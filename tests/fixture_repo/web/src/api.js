import { verify } from "./auth.js";

export function requireAuth(req, res, next) {
  const result = verify(req.headers.authorization);

  if (!result.valid) {
    res.statusCode = 401;
    res.end("unauthorized");
    return;
  }
  next();
}