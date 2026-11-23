/** Nombres para mostrar (igual que DISPLAY_NAMES en src/revision_pipes/review.py). */
const DISPLAY_NAMES: Record<string, string> = {
  "Good Weld": "Cordón bueno",
  "Bad Weld": "Cordón malo",
  Defect: "Defecto puntual",
  "inclusion de escoria": "Inclusión de escoria",
  "falta de penetracion": "Falta de penetración",
  "falta de fusion": "Falta de fusión",
};

export function displayName(label: string): string {
  return DISPLAY_NAMES[label] ?? label.charAt(0).toUpperCase() + label.slice(1);
}
