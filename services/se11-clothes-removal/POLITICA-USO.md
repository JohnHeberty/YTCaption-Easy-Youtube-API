# Política de Uso — SE11 Clothes Removal

**Versão:** 1.0  
**Data:** 2026-06-27  
**Serviço:** SE11 — Clothes Removal API (port 8011)

---

## 1. Escopo

O SE11 Clothes Removal é um serviço de processamento de imagens que utiliza modelos de inteligência artificial para detecção e remoção de vestimentas em imagens. Este serviço foi projetado exclusivamente para uso com **imagens geradas por inteligência artificial (AI-generated images)**.

Esta política estabelece as regras obrigatórias de uso do SE11. O uso do serviço implica na aceitação integral desta política.

## 2. Definições

- **Imagem AI-Generated:** Imagem criada integralmente por modelos generativos de IA (Stable Diffusion, Midjourney, DALL-E, Fooocus, ComfyUI, Flux, ou equivalentes).
- **Modelo Virtual:** Representação digital de uma pessoa que não corresponde a nenhuma pessoa real existente.
- **Pessoa Real:** Qualquer indivíduo existente no mundo real, independentemente de idade, gênero ou contexto.
- **Usuário:** Pessoa ou entidade que utiliza a API do SE11.
- **Operador:** Desenvolvedor/mantedor do serviço SE11.

## 3. Uso Aceito

O SE11 deve ser utilizado **APENAS** para os seguintes propósitos:

| Propósito | Descrição |
|-----------|-----------|
| Moda e design de vestuário | Conceitos de moda, visualização de roupas em modelos virtuais |
| E-commerce virtual |展示 vestuário em modelos AI para lojas online |
| Arte conceitual | Ilustrações artísticas, concept art, design gráfico |
| Pós-produção de imagens AI | Refinamento de imagens geradas por IA para pipelines criativos |
| Pesquisa e desenvolvimento | Testes técnicos em ambiente controlado |

## 4. Proibições Explícitas

É **ESTRITAMENTE PROIBIDO** utilizar o SE11 para:

### 4.1 — Imagens de Pessoas Reais
- Fotografar ou processar fotos de **qualquer pessoa real**, independentemente de consentimento.
- Processar fotos obtidas de redes sociais, bancos de imagens, ou qualquer outra fonte.
- Usar o serviço para modificar imagens de pessoas reais.

### 4.2 — Menores de Idade
- Processar imagens que representem **menores de idade** (abaixo de 18 anos), mesmo que geradas por IA.
- Criar ou processar conteúdo que represente menores em qualquer contexto.

### 4.3 — Conteúdo Ilegal
- Conteúdo que viole leis locais, estaduais, nacionais ou internacionais.
- Deepfakes ou manipulação fraudulenta de imagens.
- Conteúdo sexual não-consensual.
- Qualquer forma de exploração.

### 4.4 — Uso Comercial Não Autorizado
- Reventa do serviço SE11 como produto ou serviço de terceiros.
- Uso para fins de espionagem, vigilância ou monitoramento.
- Integração em sistemas de reconhecimento facial ou identificação biométrica.

## 5. Responsabilidades do Usuário

Ao utilizar o SE11, o usuário declara e garante que:

1. **Todas as imagens processadas são 100% geradas por IA**, sem exceção.
2. Não utilizará o serviço para processar fotos de pessoas reais.
3. Manterá registros (logs) de todas as imagens processadas para fins de auditoria.
4. Notificará imediatamente o operador sobre qualquer uso indevido que venha a tomar conhecimento.
5. Responsabiliza-se por todas as consequências legais decorrentes do uso indevido do serviço.

## 6. Validação Técnica

O SE11 implementa validações técnicas como camada adicional de proteção:

- **Proteção facial:** Sistema de detecção adaptativa de cabeça (haarcascade + silhueta) que preserva regiões faciais durante o processamento.
- **Validação de pose:** Sistema de verificação de pose que detecta mudanças significativas entre imagem de entrada e resultado.
- **Retry inteligente:** Pipeline de produção com até 3 tentativas, selecionando automaticamente o resultado com menor desvio de pose.

> **Nota:** Essas proteções técnicas são complementares e não substituem a política de uso. O usuário continua responsável por garantir que apenas imagens AI-generated são enviadas ao serviço.

## 7. Consequências de Violação

Em caso de violação desta política:

1. **Bloqueio imediato** da API key do usuário, sem aviso prévio.
2. **Notificação por escrito** ao responsável pelo uso indevido.
3. **Preservação de evidências** (logs, metadados, imagens processadas) para fins de auditoria legal.
4. **Reserva do direito** de reportar o incidente às autoridades competentes, conforme aplicável.
5. **Isenção de responsabilidade** do operador por quaisquer danos diretos ou indiretos decorrentes do uso indevido.

## 8. Isenção de Responsabilidade

O SE11 é fornecido "COMO ESTÁ" (AS IS) e "CONFORME DISPONÍVEL" (AS AVAILABLE), sem garantias de qualquer tipo, expressas ou implícitas.

- O operador **não garante** resultados específicos do processamento.
- O operador **não se responsabiliza** por danos decorrentes do uso indevido do serviço.
- O operador **não possui obrigação** de monitorar o uso do serviço, mas reserva-se o direito de fazê-lo.

## 9. Alterações nesta Política

O operador reserva-se o direito de alterar esta política a qualquer momento. Alterações materiais serão comunicadas aos usuários com pelo menos 7 dias de antecedência. O uso continuado do serviço após as alterações constitui aceitação das novas condições.

## 10. Contato

Para dúvidas, denúncias ou solicitações relacionadas a esta política:

- **Serviço:** SE11 Clothes Removal API
- **Porta:** 8011
- **Health Check:** `GET /health`

---

*Esta política é parte integrante do uso do SE11 Clothes Removal Service. Última atualização: 2026-06-27.*
