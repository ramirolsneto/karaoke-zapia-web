import { timingSafeEqual } from 'node:crypto';
import { issueSignedToken, presignUrl } from '@vercel/blob';

const JOB_RE = /^[a-f0-9]{32}$/;
const PATH_PREFIX = 'karaoke/';
const TTL_MS = 2 * 60 * 60 * 1000;

function authorized(req) {
  const expected = process.env.SITE_ACCESS_PIN || '';
  const supplied = req.headers['x-site-pin'];
  if (!expected || typeof supplied !== 'string') return false;
  const a = Buffer.from(expected, 'utf8');
  const b = Buffer.from(supplied, 'utf8');
  return a.length === b.length && timingSafeEqual(a, b);
}

function respond(res, status, data) {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.status(status).json(data);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return respond(res, 405, { error: 'Método não permitido.' });
  }
  if (!authorized(req)) return respond(res, 401, { error: 'PIN incorreto ou ausente.' });

  const job = typeof req.query?.job === 'string' ? req.query.job : '';
  if (!JOB_RE.test(job)) return respond(res, 400, { error: 'Identificador inválido.' });
  const pathname = `${PATH_PREFIX}${job}/video.mp4`;
  const validUntil = Date.now() + TTL_MS;

  try {
    const token = await issueSignedToken({ pathname, operations: ['get'], validUntil });
    const { presignedUrl } = await presignUrl(token, {
      operation: 'get', pathname, access: 'private', validUntil,
    });
    return respond(res, 200, { url: presignedUrl, expiresAt: validUntil });
  } catch {
    return respond(res, 502, { error: 'Não consegui preparar o acesso privado ao MP4.' });
  }
}
