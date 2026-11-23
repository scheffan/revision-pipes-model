// Copia los modelos (de ../models) a public/models para que la app los sirva.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const here = new URL("..", import.meta.url).pathname;
const models = join(here, "..", "models");
const out = join(here, "public");
mkdirSync(join(out, "models"), { recursive: true });

let faltan = [];
for (const name of ["radiografias", "cordones", "portero"]) {
  for (const ext of ["onnx", "json"]) {
    const file = `modelo_${name}.${ext}`;
    if (existsSync(join(models, file))) copyFileSync(join(models, file), join(out, "models", file));
    else faltan.push(file);
  }
}
console.log(faltan.length ? `Faltan en models/: ${faltan.join(", ")}` : "Modelos y motor listos en public/.");
