# Karaokê Zapia — interface web

Site estático para associar uma música a um link do YouTube, reproduzir no player oficial e buscar letras sincronizadas no LRCLIB. Inclui o notebook Kaggle para processamento manual autorizado com Demucs, Whisper e FFmpeg.

## Publicação no Vercel

1. Importe este repositório privado do GitHub no Vercel.
2. Selecione **Other** como framework; deixe o comando de build vazio e publique a raiz do repositório.
3. Faça o deploy e teste o endereço gerado.

## Uso

- Cole um link do YouTube para abrir o player oficial.
- Digite o título e, se quiser, artista para buscar letras no LRCLIB.
- Baixe `KaraokeZapia_GPU_Kaggle.ipynb`, adicione um áudio autorizado como dataset privado no Kaggle e execute o notebook com GPU/Internet ativados.

O site não precisa de backend nem de chave de API. Ele não baixa áudio do YouTube. A cota de GPU do Kaggle é semanal e pode variar; [consulte a documentação](https://www.kaggle.com/docs/efficient-gpu-usage).
