# Análise do Problema de Memória no Serviço de Normalização de Áudio

## 1. Identificação do Problema

O microserviço `audio-normalization` está apresentando falhas críticas ao processar arquivos de áudio grandes. A análise dos logs e do código-fonte revelou que a causa raiz do problema é o consumo excessivo de memória, que leva o sistema operacional a encerrar forçadamente os workers do Celery (processo `ForkPoolWorker`) com um sinal `SIGKILL`.

### Evidências do Log:

```
[2025-10-31 15:18:29,533: ERROR/MainProcess] Process 'ForkPoolWorker-2' pid:17 exited with 'signal 9 (SIGKILL)'
[2025-10-31 15:18:29,547: ERROR/MainProcess] Task handler raised error: WorkerLostError('Worker exited prematurely: signal 9 (SIGKILL) Job: 0.')
```

O sinal `SIGKILL` (sinal 9) é tipicamente enviado pelo *OOM (Out of Memory) Killer* do kernel Linux quando um processo consome mais memória do que a disponível no sistema.

## 2. Causa Raiz

A investigação do código no arquivo `services/audio-normalization/app/processor.py` aponta para a seguinte linha como a principal fonte do problema:

```python
# Em AudioProcessor.process_audio_job
audio = AudioSegment.from_file(job.input_file)
```

A biblioteca `pydub`, através do método `AudioSegment.from_file()`, carrega **o arquivo de áudio inteiro na memória RAM**. Para arquivos grandes (como o de 156 MB nos logs), isso resulta em um pico de consumo de memória que ultrapassa os limites do contêiner ou do sistema, ativando o OOM Killer.

Embora o código possua uma lógica para processamento em *chunks*, essa lógica só é acionada *após* o arquivo já ter sido completamente carregado na memória. Portanto, a proteção contra OOM falha antes mesmo de ser utilizada.

## 3. Estratégia de Solução

Para resolver o problema de forma definitiva, é necessário abandonar a abordagem de carregar o arquivo inteiro e adotar uma **estratégia de processamento em streaming (ou por pedaços/chunks) desde a leitura do arquivo**.

A solução proposta consiste em:

1.  **Leitura em Chunks com `ffmpeg`:** Utilizar o `ffmpeg` como um subprocesso para ler o arquivo de áudio de entrada e dividi-lo em pedaços (chunks) de duração fixa, salvando-os como arquivos temporários. Isso evita carregar o arquivo inteiro na memória.

2.  **Processamento Iterativo:** Iterar sobre cada chunk temporário, carregando apenas um pedaço de cada vez na memória para aplicar as operações de normalização (remoção de ruído, filtro high-pass, etc.).

3.  **Reconstrução do Áudio:** Após o processamento de todos os chunks, eles serão concatenados para formar o arquivo de áudio final.

4.  **Ajuste no `AudioProcessor`:**
    *   Criar uma nova função, como `_process_audio_in_chunks`, que orquestrará todo o fluxo de streaming.
    *   A função `process_audio_job` será modificada para delegar o processamento a essa nova função quando detectar que um arquivo é grande o suficiente para justificar o processamento em chunks.
    *   As funções existentes (`_remove_noise`, `_isolate_vocals`) serão adaptadas para operar em `AudioSegment` de chunks individuais.

Essa abordagem garantirá que o consumo de memória permaneça baixo e constante, independentemente do tamanho do arquivo de entrada, eliminando a causa raiz do erro `SIGKILL` e tornando o serviço robusto e escalável para arquivos de qualquer tamanho.
