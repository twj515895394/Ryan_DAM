// Stages ffmpeg/ffprobe binaries into ffmpeg-bin/ for PyInstaller bundling.
// Priority: RYAN_DAM_FFMPEG_DIR env, then PATH. When nothing is found we
// write placeholder text files (rejected at runtime by the "MZ" PE-header
// check in media_service) so the always-on --add-binary flags keep working.
import { copyFileSync, existsSync, mkdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import path from "node:path";
import process from "node:process";

const binDir = path.resolve("ffmpeg-bin");
mkdirSync(binDir, { recursive: true });
for (const name of ["ffmpeg.exe", "ffprobe.exe"]) {
  rmSync(path.join(binDir, name), { force: true });
}

function findBinary(name) {
  const candidates = [];
  const envDir = process.env.RYAN_DAM_FFMPEG_DIR;
  if (envDir) {
    candidates.push(path.join(envDir, `${name}.exe`), path.join(envDir, name));
  }
  try {
    const command = process.platform === "win32" ? `where ${name}` : `which ${name}`;
    const out = execSync(command, { stdio: ["ignore", "pipe", "ignore"] }).toString();
    for (const line of out.split(/\r?\n/)) {
      if (line.trim()) candidates.push(line.trim());
    }
  } catch {
    // binary not on PATH
  }
  for (const candidate of candidates) {
    if (existsSync(candidate) && statSync(candidate).size > 4096) return candidate;
  }
  return null;
}

const ffmpeg = findBinary("ffmpeg");
const ffprobe = findBinary("ffprobe");
let bundled = false;

if (ffmpeg && ffprobe) {
  copyFileSync(ffmpeg, path.join(binDir, "ffmpeg.exe"));
  copyFileSync(ffprobe, path.join(binDir, "ffprobe.exe"));
  bundled = true;
  console.log(`prepare-ffmpeg: staged ${ffmpeg} and ${ffprobe}`);
} else {
  writeFileSync(
    path.join(binDir, "ffmpeg.exe"),
    "PLACEHOLDER - ffmpeg was not found at build time; runtime falls back to icons.\n"
  );
  writeFileSync(
    path.join(binDir, "ffprobe.exe"),
    "PLACEHOLDER - ffprobe was not found at build time; runtime falls back to icons.\n"
  );
  console.log("prepare-ffmpeg: ffmpeg not found; bundling placeholders (runtime degrades gracefully)");
}

writeFileSync(path.join(binDir, "manifest.json"), JSON.stringify({ bundled }, null, 2));
