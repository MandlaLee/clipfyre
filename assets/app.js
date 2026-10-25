const $ = (id) => document.getElementById(id);
const dz = $('dropzone');
const fileInput = $('fileinput');
const browseBtn = $('browseBtn');
const workspace = $('workspace');
const video = $('video');
const filenameEl = $('filename');
const filesizeEl = $('filesize');
const chopBtn = $('chopBtn');
const resetBtn = $('resetBtn');
const progress = $('progress');
const logEl = $('log');
const cmdEl = $('cmd');
const steps = ['transcribe', 'detect', 'cut'];

let currentFile = null;
let videoUrl = null;

const fmtBytes = (n) => {
  if (!n) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let unit = 0;
  while (n >= 1024 && unit < units.length - 1) {
    n /= 1024;
    unit++;
  }
  return `${n.toFixed(1)} ${units[unit]}`;
};

function showFile(file) {
  if (!file) return;
  if (!file.type.startsWith('video/')) {
    alert('Please choose a video file.');
    return;
  }

  if (videoUrl) URL.revokeObjectURL(videoUrl);
  currentFile = file;
  videoUrl = URL.createObjectURL(file);
  filenameEl.textContent = file.name;
  filesizeEl.textContent = fmtBytes(file.size);
  video.src = videoUrl;
  dz.hidden = true;
  workspace.hidden = false;
  progress.hidden = true;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

browseBtn.addEventListener('click', (event) => {
  event.stopPropagation();
  fileInput.click();
});
dz.addEventListener('click', () => fileInput.click());
dz.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener('change', () => showFile(fileInput.files[0]));

['dragenter', 'dragover'].forEach((eventName) => {
  dz.addEventListener(eventName, (event) => {
    event.preventDefault();
    dz.classList.add('drag');
  });
});
['dragleave', 'drop'].forEach((eventName) => {
  dz.addEventListener(eventName, (event) => {
    event.preventDefault();
    dz.classList.remove('drag');
  });
});
dz.addEventListener('drop', (event) => showFile(event.dataTransfer.files[0]));

function shellQuote(value) {
  return `'${value.replaceAll("'", "'\\''")}'`;
}

function buildCommand() {
  const name = currentFile ? currentFile.name : 'input.mp4';
  const top = $('top').value || 5;
  const min = $('minlen').value || 15;
  const max = $('maxlen').value || 60;
  return `python -m clipfyre ${shellQuote(name)} --out ./shorts --top ${top} --min ${min} --max ${max}`;
}

function setStep(name, state) {
  const step = document.querySelector(`.steps li[data-step="${name}"]`);
  if (!step) return;
  step.classList.toggle('active', state === 'active');
  step.classList.toggle('done', state === 'done');
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function runDemo() {
  progress.hidden = false;
  logEl.textContent = '';
  cmdEl.textContent = buildCommand();
  steps.forEach((step) => setStep(step, ''));

  logEl.textContent = `$ ${buildCommand()}\n[1/3] transcribing ${currentFile?.name || 'input.mp4'} ...\n`;
  setStep('transcribe', 'active');
  await delay(900);
  setStep('transcribe', 'done');

  setStep('detect', 'active');
  logEl.textContent += '[2/3] detecting moments ...\n';
  await delay(700);
  setStep('detect', 'done');

  setStep('cut', 'active');
  logEl.textContent += '[3/3] cutting shorts ...\n';
  await delay(800);
  setStep('cut', 'done');

  logEl.textContent +=
    '  -> ./shorts/short_01.mp4  (32.4s)\n' +
    '  -> ./shorts/short_02.mp4  (28.1s)\n' +
    '  -> ./shorts/short_03.mp4  (41.7s)\n' +
    '\n✓ done. (demo — run the command locally to make real files)\n';
}

chopBtn.addEventListener('click', runDemo);

resetBtn.addEventListener('click', () => {
  currentFile = null;
  if (videoUrl) URL.revokeObjectURL(videoUrl);
  videoUrl = null;
  video.removeAttribute('src');
  video.load();
  workspace.hidden = true;
  progress.hidden = true;
  dz.hidden = false;
  fileInput.value = '';
});

$('copyCmd').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(cmdEl.textContent);
    $('copyCmd').textContent = 'Copied ✓';
    setTimeout(() => {
      $('copyCmd').textContent = 'Copy command';
    }, 1500);
  } catch {
    alert('Copy failed — select the command text and copy manually.');
  }
});
