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

/** Tipos que el inspector puede elegir al corregir un hallazgo, por imagen. */
export const TIPOS_POR_IMAGEN = {
  radiografia: ["porosidad", "fisura", "inclusion de escoria", "falta de penetracion", "falta de fusion", "otro defecto"],
  foto: ["Bad Weld", "Defect"],
} as const;
