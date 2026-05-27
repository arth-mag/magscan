# MagScan — Sistema Embarcado de Escaneamento de MTG

Este repositório contém a base modular para o **MagScan**, um sistema robusto e eficiente de Visão Computacional (Edge AI) para identificação automatizada e inventário de cartas físicas de *Magic: The Gathering*.

## Estrutura de Pastas e Arquivos

O projeto foi estruturado com base nas diretrizes do documento de design de software (SDD) em módulos coesos e bem-definidos:

* **`src/config.py`**: Parâmetros estáticos do sistema, constantes físicas de câmera, margens de cortes geométricos (caixas de título e de arte do card) e limites de similaridade OCR/dHash.
* **`src/database.py`**: Gerenciador de conexão com o banco SQLite relacional `cards.db`. Cria índices automáticos rápidos em árvore para buscas hiper-rápidas em tempo real e cuida da tabela complementar de dHashes.
* **`src/card_vision.py`**: Responsável pelo processamento de imagem inicial. Reduz escala, aplica filtros de borda (Canny + Morfologia), localiza contornos candidatos baseando-se no aspecto real do card e planifica a imagem com transformação perspectiva 3D (`warpPerspective`).
* **`src/text_extractor.py`**: Processa a caixa de título recortada (upscaling + binarização adaptativa) e utiliza o motor **Pytesseract OCR** associado ao **RapidFuzz** para corrigir automaticamente possíveis leituras errôneas.
* **`src/hash_matcher.py`**: Implementa o algoritmo Difference Hash (dHash) puro e rápido de 64-bits nas artes das cartas, permitindo resolver a impressão exata comparando distância de Hamming contra as variantes possíveis.
* **`src/main.py`**: O script orquestrador central. Inicia a captura de vídeo, processa o fluxo de frames e executa a persistência assíncrona das leituras em um inventário JSON (`inventario.json`).

---

## Requisitos de Ambiente

Para rodar o scanner localmente, certifique-se de ter o **Tesseract OCR** instalado no sistema operacional:

```bash
# Ubuntu / Debian / Armbian
sudo apt-get update
sudo apt-get install tesseract-ocr
```

## Como Executar o Sistema

1. **Instalar Dependências**:
   Ative o ambiente virtual e instale as bibliotecas listadas no `requirements.txt`:
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Iniciar o Escaneamento**:
   Execute o script principal:
   ```bash
   python -m src.main
   ```
   * Pressione a tecla `q` para sair e fechar a visualização do vídeo.
   * O inventário das cartas lidas com sucesso será salvo no arquivo local `inventario.json`.
