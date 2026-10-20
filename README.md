# Karaokê Zapia — interface web

Site estático para informar um link compartilhado do MukaPlay, ajustar o tom e preparar a configuração para o notebook Kaggle. O notebook baixa o MP4 compartilhado, extrai o áudio com FFmpeg, separa a voz com Demucs, sincroniza a letra com Whisper e gera o MP4 do videokê.

## Publicação no Vercel

1. Importe este repositório privado do GitHub no Vercel.
2. Selecione **Other** como framework; deixe o comando de build vazio e publique a raiz do repositório.
3. Faça o deploy e teste o endereço gerado.

## Uso

- Cole um link de compartilhamento MukaPlay no formato `/dynps/share/...` e confirme que tem direito/permissão para processar o conteúdo.
- Escolha o tom entre -6 e +6 semitons e baixe `karaoke_settings.json`.
- Baixe `KaraokeZapia_GPU_Kaggle.ipynb`, ative GPU e Internet e cole o link diretamente em `MUKA_URL`, ou adicione o JSON como uma entrada privada do Kaggle.
- O notebook busca o MP4 da página compartilhada, extrai o áudio e gera instrumental, SRT e MP4 de videokê. A transcrição de canto pode conter erros; revise o SRT.

O site só valida o formato do link e cria a configuração; o processamento acontece ao executar manualmente o notebook Kaggle. O site não faz download nem gera MP4 sozinho. A página do MukaPlay pode expor os downloads em MP4; a disponibilidade depende do link. A cota de GPU do Kaggle é semanal e pode variar; [consulte a documentação](https://www.kaggle.com/docs/efficient-gpu-usage).
