# GUIA DE GRAVACAO PARA CLONAGEM DE VOZ - CHATTERBOX TTS

## OBJETIVO

Este guia explica como gravar um audio de referencia ideal para obter a melhor qualidade
possivel na clonagem de voz usando o modelo Chatterbox Multilingual (PT-BR).

---

## 1. DURACAO

| Parametro | Valor Recomendado |
|---|---|
| Minimo absoluto | 5 segundos |
| **Ideal** | **10 a 15 segundos** |
| Maximo util | 15 segundos |

> O modelo usa apenas os primeiros 6-10 segundos do audio de referencia.
> Audio maior que 15s causa media de prosodia e reduz a qualidade da clonagem.

---

## 2. FORMATO DO ARQUIVO

| Parametro | Valor Ideal |
|---|---|
| Formato | WAV (PCM) |
| Canais | Mono (1 canal) |
| Sample rate | 24000 Hz (ou superior: 44100/48000) |
| Bits | 16-bit |

---

## 3. AMBIENTE DE GRAVACAO

### O QUE FAZER
- Grave em um **comodo silencioso** e fechado
- Use um espaco pequeno com superficies macias (armario, cobertores, cortinas)
- Se possivel, grave dentro de um **closet** ou cabine improvisada
- Feche portas e janelas
- Desligue ventiladores, ar-condicionado, geladeira (se proximo)
- Use **fone de ouvido** para ouvir musica/referencia durante a gravacao

### O QUE NAO FAZER
- Nao grave em cozinha, banheiro ou comodo com eco
- Nao grave ao ar livre (vento, barulho de rua)
- Nao grave perto de janelas abertas
- Nao grave com ventilador/AC ligado
- Nao grave com outros falando ao fundo

---

## 4. MICROFONE

### Opcoes por ordem de qualidade

1. **Microfone condensador USB** (Blue Yeti, AT2020USB+, Samson C01) - IDEAL
2. **Microfone de gravador digital** (Zoom H1n, Tascam DR-05X) - EXCELENTE
3. **Fone de ouvido com microfone embutido** (AirPods, headset gamer) - ACEITAVEL
4. **Microfone embutido do celular/laptop** - EVITAR

### Posicionamento
- Distancia: **15-25 cm** da boca (mao aberta de distancia)
- Angulo: ligeiramente abaixo ou ao lado da boca (evitar rajadas de ar)
- Use um **pop filter** ou pano fino na frente do microfone
- Fixe o microfone em suporte estavel (nao segure na mao)

---

## 5. SCRIPT DE GRAVACAO - FRASES FONETICAMENTE BALANCEADAS

O tipo de legenda que voce precisa sao **frases foneticamente balanceadas**.
Sao frases selecionadas cientificamente para cobrir todos os fonemas do portugues
brasileiro com a mesma frequencia que aparecem na fala natural.

Isso garante que o modelo capture:
- Todos os sons da lingua (vogais, consoantes, diphthongs)
- Variacoes de entonacao natural
- Prosodia representativa da fala cotidiana

### COMO USAR

1. Grave lendo **exatamente** as frases abaixo em voz alta
2. Fale no seu **ritmo natural** - nem rapido nem devagar
3. Use entonacao natural - como se estivesse conversando
4. Pare apos **10 a 15 segundos** (nao precisa terminar todas)
5. Grave em um unico take, sem cortes

### SCRIPT PARA GRAVACAO (copie e leia em voz alta)

```
Pesquisa e uma coisa que muda a toda hora. No total, serao chamados
vinte e seis mil candidatos. O numero de convocados por vaga e de doze
candidatos. Atualmente, esse abatimento e limitado a setenta por cento
dos gastos. Sandra Regina Machado: acho que ela enfim criou juizo.
Eles estao colocando armadilhas nas fazendas onde ja ocorreram os ataques.
```

> Fonte: 1000 Frases Foneticamente Balanceadas para PT-BR
> (Cirigliano et al., 2005 - SBrT)

### DICAS DE LEITURA

- Leia como se estivesse **contando uma historia** para um amigo
- Nao leia como se estivesse lendo uma lista
- Inclua **variacoes de entonacao**: perguntas sobem, declaracoes descem
- Nao faca pausas longas entre frases
- Nao grite, nao sussurre - fale no **tom normal** da sua voz
- Nao ria, nao tosa, nao limpe a garganta

---

## 6. O QUE EVITAR NO AUDIO

- Palavras soltas ou enumeracoes ("um, dois, tres, quatro...")
- Texto monotonico sem variacao de entonacao
- Leitura robotica ou monotona
- Gritar ou sussurrar
- Pausas longas e silenciosas entre frases
- Riso, tosse ou sons nao verbais
- Musica ou sons ao fundo
- Frases muito longas (max 250 caracteres por frase)

---

## 7. ESTILO DE FALA

| Estilo do Audio Referencia | Resultado na Geracao |
|---|---|
| Calmo e pausado | Geracao calma e pausada |
| Rapido e energico | Geracao rapida e energica |
| Narracao de audiolivro | Geracao estilo audiolivro |
| Conversacional informal | Geracao informal |

> **REGRA DE OURO:** O estilo do audio de referencia define o estilo da geracao.
> Se quero gerar audiolivro, grave a referencia no estilo de audiolivro.

---

## 8. PARAMETROS DO MODELO

### Padrao (recomendado para maioria dos casos)

| Parametro | Padrao | Descricao |
|---|---|---|
| `exaggeration` | **0.5** | Intensidade emocional (0.0 neutro, 1.0+ dramatico) |
| `cfg_weight` | **0.5** | Quanto segue a referencia (0.0 livre, 1.0 identico) |
| `temperature` | **0.8** | Aleatoriedade (0.4 consistente, 1.0+ criativo) |

### Tabela de ajuste fino

| Situacao | exaggeration | cfg_weight | Resultado |
|---|---|---|---|
| Voz neutra e natural | 0.5 | 0.5 | Padrao - funciona bem |
| Voz expressiva e dramatica | 0.7-0.8 | 0.3 | Mais emocao, ritmo mais lento |
| Voz rapida e direta | 0.3-0.4 | 0.3 | Mais rapido e direto |
| Voz calma e pausada | 0.5 | 0.6-0.7 | Mais pausado e deliberado |
| Maximizar similaridade | 0.5 | 0.7 | Mais fiel a referencia |

### IMPORTANTE

- **Aumentar `exaggeration`** = voz mais expressiva, MAS tende a **acelerar** a fala
- **Diminuir `cfg_weight`** = compensa aceleracao, fala mais lenta e deliberada
- **Diminuir `cfg_weight`** = modelo segue menos a referencia, pode perder timbre
- **Aumentar `cfg_weight`** = modelo segue mais a referencia, mais fiel ao original

---

## 9. CONVERSAO COM FFMPEG

Se seu audio nao estiver no formato ideal:

```bash
# Converter para WAV mono 24kHz 16-bit, primeiros 15 segundos
ffmpeg -i input.mp3 -t 15 -ac 1 -ar 24000 -acodec pcm_s16le output.wav

# Converter de qualquer formato para WAV 24kHz mono
ffmpeg -i input.ogg -ac 1 -ar 24000 output.wav

# Normalizar volume (recomendado)
ffmpeg -i input.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11" output_normalized.wav
```

---

## 10. CHECKLIST ANTES DE ENVIAR

- [ ] Audio tem entre 10 e 15 segundos
- [ ] Formato WAV, mono, 24kHz (ou superior)
- [ ] Ambiente silencioso sem eco
- [ ] Apenas UMA pessoa falando
- [ ] Leu as frases foneticamente balanceadas (secao 5)
- [ ] Faleu no ritmo natural (nao lerapido nem devagar)
- [ ] Usou entonacao variada (perguntas sobem, declaracoes descem)
- [ ] Sem ruidos de fundo
- [ ] Microfone a 15-25 cm da boca
- [ ] Sem pausas longas entre frases
- [ ] Sem tosse, riso ou sons nao verbais

---

## 11. DIAGNOSTICO DE PROBLEMAS

| Problema | Causa Provavel | Solucao |
|---|---|---|
| Voz gerada nao se parece | Audio de referencia com ruido | Regrave em ambiente mais silencioso |
| Voz gerada e robotic | Audio de referencia com eco | Grave em espaco menor com superficies macias |
| Voz muito lenta e grossa | exaggeration alto + cfg_weight baixo | Use padrao: exaggeration=0.5, cfg_weight=0.5 |
| Voz muito rapida | cfg_weight muito baixo | Aumente cfg_weight para 0.5-0.6 |
| Voz muito devagar | cfg_weight muito alto | Reduza cfg_weight para 0.3-0.4 |
| Audio gerado corta no meio | Texto muito longo | Divida em frases de ate 250 caracteres |
| Sotaque diferente | Idioma do audio != idioma do texto | Use audio no mesmo idioma do texto gerado |
| Audio gerado tem artefatos | Texto muito longo por chunk | Reduza chunk_size ou divida o texto |
| Voz nao expressiva | exaggeration muito baixo | Aumente exaggeration para 0.7-0.8 |

---

## REFERENCIAS

- ResembleAI Chatterbox Docs: https://github.com/resemble-ai/chatterbox
- Issue #39 - Audio Clip Guidelines: https://github.com/resemble-ai/chatterbox/issues/39
- Chatterbox Multilingual PT-BR: https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br
- 1000 Frases Foneticamente Balanceadas PT-BR: https://github.com/topological-modular-forms/1000-Phonetically-Balanced-Sentences-in-Brazilian-Portuguese
- Cirigliano et al. (2005) - SBrT
