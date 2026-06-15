OBS o .env na raiz do projeto tem HUGGINGFACE_TOKEN para que possa baixar o modelo para geracao de audio 



Sim. Para rodar **o PT-BR dedicado**, eu não começaria pelo `pip install chatterbox-tts` puro, porque isso tende a puxar o Chatterbox geral. O caminho mais seguro é clonar o **Space oficial PT-BR**, que já está configurado com `ResembleAI/Chatterbox-Multilingual-pt-br`, `language_id='pt'`, interface Gradio e parâmetros de `exaggeration`, `temperature` e `cfg_weight`. O próprio model card diz que esse checkpoint é otimizado para português brasileiro e usa `language_id: pt`; o Space oficial mostra que ele é “fine-tuned for Brazilian Portuguese”. ([Hugging Face][1]) ([Hugging Face][2])

## Caminho mais simples: rodar a interface local

Recomendo usar **Linux ou WSL2 Ubuntu**. O repositório oficial diz que o Chatterbox foi testado com **Python 3.11** e pode ser instalado por `pip install chatterbox-tts` ou via source; o Space PT-BR usa PyTorch/Torchaudio 2.8.0, Gradio, librosa, s3tokenizer, transformers, diffusers, resemble-perth e outros pacotes. ([GitHub][3]) ([Hugging Face][4])

```bash
# 1) Crie o ambiente
conda create -n chatterbox-ptbr python=3.11 -y
conda activate chatterbox-ptbr

# 2) Clone o Space PT-BR oficial
git clone https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br
cd Chatterbox-Multilingual-TTS-pt-br

# 3) Instale as dependências
pip install -r requirements.txt

# 4) Rode a interface
python app.py
```

Depois disso, abra o endereço local que o Gradio mostrar, normalmente algo como:

```text
http://127.0.0.1:7860
```

Na tela, você coloca o texto em português, opcionalmente sobe um áudio de referência, ajusta `Exaggeration`, `CFG/Pace` e `Temperature`, e gera o `.wav`.

## Script mínimo sem interface

Depois de clonar o Space PT-BR e instalar o `requirements.txt`, crie um arquivo chamado `gerar_audio.py` dentro da pasta:

```python
import torch
import torchaudio as ta
from chatterbox.src.chatterbox.tts import ChatterboxTTS

device = "cuda" if torch.cuda.is_available() else "cpu"

model = ChatterboxTTS.from_pretrained(device)

texto = """
Ela olhou para a porta.

Esperou.

Nada aconteceu.

Então... ouviu uma voz do outro lado.

Você não devia ter voltado.
"""

wav = model.generate(
    texto[:300],
    language_id="pt",
    exaggeration=0.75,
    temperature=0.8,
    cfg_weight=0.35,
)

ta.save("saida_ptbr.wav", wav, model.sr)
print("Gerado: saida_ptbr.wav")
```

Rode:

```bash
python gerar_audio.py
```

O arquivo sai como:

```text
saida_ptbr.wav
```

## Para usar uma voz de referência

O app oficial usa áudio de referência opcional; no código do Space, quando existe `audio_prompt_path`, ele passa esse arquivo para `model.generate(...)`. ([Hugging Face][2])

Use um `.wav` curto, de preferência **5 a 15 segundos**, limpo, sem música, sem ruído, e com a voz que você tem permissão para usar:

```python
wav = model.generate(
    texto[:300],
    language_id="pt",
    audio_prompt_path="minha_voz.wav",
    exaggeration=0.75,
    temperature=0.8,
    cfg_weight=0.35,
)
```

## Ajustes para fala dramática

O README oficial recomenda, para fala expressiva/dramática, usar `cfg_weight` mais baixo, por exemplo `~0.3`, e `exaggeration` perto de `0.7` ou mais; ele também avisa que exagero alto pode acelerar a fala, então reduzir `cfg_weight` ajuda a compensar com ritmo mais deliberado. ([GitHub][3])

Use assim para drama:

```python
exaggeration=0.8
cfg_weight=0.3
temperature=0.8
```

Use assim para voz mais neutra:

```python
exaggeration=0.5
cfg_weight=0.5
temperature=0.8
```

## Observação importante sobre pausas

O Chatterbox normaliza parte da pontuação internamente; no código, por exemplo, reticências podem ser convertidas para vírgula durante a normalização. ([GitHub][5]) Então, para pausas dramáticas, o melhor resultado costuma vir de **frases curtas e blocos separados**, não só de vírgulas:

```text
Eu achei que era simples.

Mas não era.

Quando a porta se abriu...

ninguém disse uma palavra.

Só o vento entrou.
```




Para pausas realmente exatas, gere em blocos separados e depois una com silêncio via `pydub`/`ffmpeg`. O modelo é bom para expressividade, mas não é um motor SSML com `<break time="800ms"/>`.

[1]: https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br "ResembleAI/Chatterbox-Multilingual-pt-br · Hugging Face"
[2]: https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br/blob/main/app.py "app.py · ResembleAI/Chatterbox-Multilingual-TTS-pt-br at main"
[3]: https://github.com/resemble-ai/chatterbox "GitHub - resemble-ai/chatterbox: SoTA open-source TTS · GitHub"
[4]: https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br/blob/main/requirements.txt "requirements.txt · ResembleAI/Chatterbox-Multilingual-TTS-pt-br at main"
[5]: https://github.com/resemble-ai/chatterbox/blob/master/src/chatterbox/mtl_tts.py "chatterbox/src/chatterbox/mtl_tts.py at master · resemble-ai/chatterbox · GitHub"
