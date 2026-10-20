import { timingSafeEqual } from 'node:crypto';

const JOB_RE = /^[a-f0-9]{32}$/;
const KAGGLE_USERNAME_RE = /^[A-Za-z0-9_-]+$/;

function authorized(req) {
  const expected = process.env.SITE_ACCESS_PIN || '';
  const supplied = req.headers['x-site-pin'];
  if (!expected || typeof supplied !== 'string') return false;

  const expectedBuffer = Buffer.from(expected, 'utf8');
  const suppliedBuffer = Buffer.from(supplied, 'utf8');
  return expectedBuffer.length === suppliedBuffer.length &&
    timingSafeEqual(expectedBuffer, suppliedBuffer);
}

function respond(res, status, data) {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  return res.status(status).json(data);
}

export default function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return respond(res, 405, { error: 'Método não permitido.' });
  }
  if (!authorized(req)) {
    return respond(res, 401, { error: 'PIN incorreto ou ausente.' });
  }

  const job = typeof req.query?.job === 'string' ? req.query.job : '';
  if (!JOB_RE.test(job)) {
    return respond(res, 400, { error: 'Identificador inválido.' });
  }

  const username = (process.env.KAGGLE_USERNAME || '').trim();
  if (!KAGGLE_USERNAME_RE.test(username)) {
    return respond(res, 503, { error: 'Conta Kaggle não configurada.' });
  }

  const slug = `karaoke-zapia-${job}`;
  const url = `https://www.kaggle.com/code/${encodeURIComponent(username)}/${encodeURIComponent(slug)}`;
  return respond(res, 200, { url, message: 'Página de saída do processamento no Kaggle.' });
}
