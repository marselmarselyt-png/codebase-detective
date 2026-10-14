export function verify(token) {
  if (!token) return false;
  return token.split(".").length === 3;
}

export function currentUser(token) {
  return {
    authenticated: verify(token),
    subject: token ? token.split(".")[0] : null,
  };
}