/** Redact exact known secret values from operationally displayed text. */
export function redactSecrets(text: string, secrets: string[]): string {
  if (!text || secrets.length === 0) return text;

  const sorted = [...secrets].sort((a, b) => b.length - a.length);
  let output = text;
  for (const secret of sorted) {
    if (!secret || !output.includes(secret)) continue;
    output = output.split(secret).join('[REDACTED]');
  }
  return output;
}
