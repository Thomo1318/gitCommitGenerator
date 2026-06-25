import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Setup paths
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sopPath = path.resolve(__dirname, '../config/gitops_agent_sop.json');
const commitMsgFile = process.argv[2];
if (!commitMsgFile) {
    console.error(`\n❌ COMMIT FAILED: Missing commit message file argument.\n`);
    process.exit(1);
}

const safePath = path.resolve(process.cwd(), commitMsgFile);
const relativePath = path.relative(process.cwd(), safePath);
if (relativePath.startsWith(`..${path.sep}`) || relativePath === '..' || path.isAbsolute(relativePath)) {
    console.error(`\n❌ COMMIT FAILED: Path traversal detected.\n`);
    process.exit(1);
}

if (!fs.existsSync(safePath)) {
    console.error(`\n❌ COMMIT FAILED: Commit message file not found.\n`);
    process.exit(1);
}

// Load the SOP
const sop = JSON.parse(fs.readFileSync(sopPath, 'utf8'));
const matrix = sop.gitmoji_reference_matrix;

const rawMsg = fs.readFileSync(safePath, 'utf8');
const lines = rawMsg.split('\n').filter(line => !line.trim().startsWith('#'));
if (lines.length === 0) {
    console.error(`\n❌ COMMIT FAILED: Empty commit message.\n`);
    process.exit(1);
}

const subjectLine = lines[0].trim();

// Regex to capture: Emoji (unicode or shortcode), CC Type, Scope (optional), Breaking (!), and Subject
// Example match: "✨ feat(auth)!: add login" -> ["✨", "feat", "auth", "!", "add login"]
// Example match: ":sparkles: feat(auth)!: add login" -> [":sparkles:", "feat", "auth", "!", "add login"]
const commitRegex = /^((?:[\p{Emoji_Presentation}\p{Extended_Pictographic}\uFE0F\u200D]+|:[a-z0-9_]+:))\s+([a-z]+)(?:\(([a-z0-9\-,\s]+)\))?(!?):\s+(.+)$/u;

const match = subjectLine.match(commitRegex);

if (!match) {
    console.error(`\n❌ COMMIT FAILED: Invalid Hybrid Syntax.`);
    console.error(`Expected: <emoji> <cc_type>(<scope>): <subject>`);
    console.error(`Received: ${subjectLine}\n`);
    process.exit(1);
}

const [ , rawEmoji, ccType, scope, breaking, subject ] = match;
const emoji = rawEmoji.replace(/\uFE0F/g, '');

// Rule 1: Validate length
if (subjectLine.length > 72) {
    console.error(`\n❌ COMMIT FAILED: Subject line exceeds 72 characters (${subjectLine.length}/72).\n`);
    process.exit(1);
}

// Rule 2: Validate the Emoji and CC Type against the SOP Matrix
const validEntry = matrix.find(item => item.emoji.replace(/\uFE0F/g, '') === emoji || item.code === rawEmoji);

if (!validEntry) {
    console.error(`\n❌ COMMIT FAILED: The emoji '${rawEmoji}' is not in the GitOps SOP.\n`);
    process.exit(1);
}

if (validEntry.cc_type !== ccType) {
    console.error(`\n❌ COMMIT FAILED: Emoji / Type mismatch!`);
    console.error(`According to the SOP, '${rawEmoji}' MUST be paired with type '${validEntry.cc_type}'.`);
    console.error(`You used: '${rawEmoji} ${ccType}'.\n`);
    process.exit(1);
}

console.log(`\n✅ Commit Validated: ${validEntry.semver_impact} impact detected.\n`);
process.exit(0);
