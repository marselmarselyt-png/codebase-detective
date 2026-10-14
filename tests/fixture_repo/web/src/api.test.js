import { requireAuth } from "./api.js";

const GOOD = "header.payload.signature";
const BAD = "header.payload";

let failed = false;

function check(name, fn, expected) {
  let actual;
  try {
    actual = fn();
  } catch (err) {
    actual = `threw: ${err.message}`;
  }
  const ok = actual === expected;
  if (!ok) failed = true;
  console.log(`${ok ? "ok  " : "FAIL"} ${name}: expected ${expected}, got ${actual}`);
}

check("valid token passes the guard", () => {
  let passed = false;
  const res = { statusCode: 200, end: () => {} };
  requireAuth({ headers: { authorization: GOOD } }, res, () => {
    passed = true;
  });
  return passed;
}, true);

check("invalid token is rejected", () => {
  let nextCalled = false;
  const res = { statusCode: 200, end: () => {} };
  requireAuth({ headers: { authorization: BAD } }, res, () => {
    nextCalled = true;
  });
  return res.statusCode === 401 && !nextCalled;
}, true);

process.exit(failed ? 1 : 0);