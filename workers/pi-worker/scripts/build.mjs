import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

await build({
	entryPoints: [join(root, "src", "main.ts")],
	outfile: join(root, "dist", "main.js"),
	bundle: true,
	platform: "node",
	format: "esm",
	target: "node22",
	loader: { ".md": "text" },
	banner: {
		js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);",
	},
});
