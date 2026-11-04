import {build} from "esbuild";
import {readFile, readdir, writeFile} from "node:fs/promises";

await build({
  entryPoints: ["frontend/pilot.js"],
  bundle: true,
  format: "esm",
  target: "es2020",
  outfile: "library/static/library/generated/editor-pilot.js",
  metafile: true,
}).then(async result => {
  const packages = new Set(Object.keys(result.metafile.inputs).map(path => {
    const parts = path.split("/");
    const index = parts.lastIndexOf("node_modules");
    if (index < 0) return null;
    return parts[index + 1]?.startsWith("@")
      ? parts.slice(index + 1, index + 3).join("/") : parts[index + 1];
  }).filter(Boolean));
  const licenses = [];
  for (const name of [...packages].sort()) {
    const root = `node_modules/${name}`;
    const manifest = JSON.parse(await readFile(`${root}/package.json`, "utf8"));
    const paths = (await readdir(root)).filter(path => /^license/i.test(path)).sort();
    if (!paths.length) throw new Error(`Missing bundled dependency license: ${name}`);
    licenses.push(`${name} ${manifest.version}\n${await readFile(`${root}/${paths[0]}`, "utf8")}`);
  }
  await writeFile("library/static/library/generated/editor-licenses.txt", licenses.join("\n\n"));
});
