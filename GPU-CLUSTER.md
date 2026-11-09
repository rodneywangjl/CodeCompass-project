# CodeCompass on the SCIS GPU cluster (command line)

How to run CodeCompass with the `dev` profile (Qwen2.5-Coder-14B) on one RTX 3090 node of the SCIS GPU cluster. For the same setup from a Jupyter notebook, see [`notebooks/codecompass_gpu_cluster.ipynb`](notebooks/codecompass_gpu_cluster.ipynb). For local machines, see [`README.md`](README.md#running-fast-on-a-gpu) and [`MODEL-SETUP.md`](MODEL-SETUP.md).

## Before you start

CodeCompass runs on one GPU node as two programs: `llama-server` (the model) in the background and the `codecompass` command in front. The one-time setup takes up to an hour; after that, a session starts in about five minutes.

- **Account:** use your own SCIS cluster account and never share it. Each of us does the one-time setup in our own home folder.
- **Network:** connect to the GlobalProtect VPN (only one VPN at a time). In the commands below, replace `<cluster-address>` with the cluster's VPN address from the SCIS cluster instructions. The cluster's hostname may resolve to an on-campus address that times out over the VPN, so use the VPN address instead.
- **Limits:** our accounts are on the `student` partition with QoS `studentqos`: 4 CPUs, 32 GB of RAM and 1 GPU per job, 1 day per job, and 2 running jobs at once. A `mynotebook` session counts as one of those jobs. Run `myinfo` to check yours.
- **Storage:** nothing on the cluster is backed up, and scratch files older than 30 days are deleted.
- **Secrets:** never put passwords or tokens in any file on the cluster.

## Get a 3090 GPU shell

Always ask for an RTX 3090. Other cards in the `student` partition either lack the memory (the 1080 Ti has 11 GB) or need a different llama.cpp build.

1. Log in from Terminal (macOS) or PowerShell (Windows):

   ```bash
   ssh <your-username>@<cluster-address>
   ```

2. Clear any Slurm settings left over from an earlier job. Without this, `srun` can fail with *Memory required by task is not available*:

   ```bash
   unset $(env | grep -o '^SLURM_[A-Z_]*')
   ```

3. Ask for a GPU shell on a 3090 node:

   ```bash
   srun --pty --qos=studentqos --partition=student --gres=gpu:1 --constraint=3090 -c 4 --mem=24G bash
   ```

4. The prompt changes from `origami` to a 3090 node (aloha, lava, toga or voodoo). Run `nvidia-smi` and check it says **RTX 3090**.

If the 3090s are busy, `--constraint="3090|a40"` also accepts an A40, which is the same GPU generation with 48 GB.

## One-time setup

Do this once, inside a 3090 GPU shell, except step 1, which runs on your laptop. If you already ran the GPU notebook's setup, llama.cpp and the model are already in your home folder: skip steps 4 and 5.

1. **Upload the project.** On your laptop, in a new Terminal window, with the VPN on. Change the first path to where your copy lives:

   ```bash
   rsync -av \
     --exclude '.venv' --exclude '__pycache__' --exclude '.git' --exclude 'runs' \
     --exclude 'idx' --exclude '.pytest_cache' --exclude '.DS_Store' \
     "/path/to/CodeCompass-project/" \
     <your-username>@<cluster-address>:~/CodeCompass-project/
   ```

   Keep the `/` at the end of the first path. On Windows without `rsync`, zip the folder (leaving out the same folders) and send it with `scp CodeCompass-project.zip <your-username>@<cluster-address>:~`, then `unzip` it on the cluster.

2. **Create a Python environment.** The system Python is 3.9, which is too old, so load 3.12:

   ```bash
   module load Python/3.12.8-GCCcore-13.3.0
   python3 -m venv ~/cc-venv
   source ~/cc-venv/bin/activate
   pip install --upgrade pip
   cd ~/CodeCompass-project
   pip install -r requirements.txt
   pip install -e .
   ```

   `pip install -e .` creates the `codecompass` command. PyTorch is several GB, so this takes 5 to 15 minutes.

3. **Clone the repo to ask about.** Use Flask, never `fastapi/fastapi`, which is reserved for evaluation:

   ```bash
   git clone https://github.com/pallets/flask ~/repos/flask
   ```

4. **Build llama-server.** The prebuilt binaries need glibc 2.38 and the cluster has 2.34, so build the pinned release b11960 from source. Build on the 3090 node so it targets that GPU. This takes 10 to 30 minutes:

   ```bash
   module load CUDA/12.6.0
   pip install cmake
   git clone --depth 1 --branch b11960 https://github.com/ggml-org/llama.cpp ~/llama.cpp-src
   cd ~/llama.cpp-src
   cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
   cmake --build build --config Release -j 4 --target llama-server
   ```

   So far this build has only been done inside the notebook; these shell commands are untested. If `module load CUDA/12.6.0` fails, run `module avail CUDA` and pick the 12.6 module.

5. **Download the model (about 9 GB) and check it:**

   ```bash
   mkdir -p ~/.cache/codecompass/models && cd ~/.cache/codecompass/models
   curl -L -o qwen2.5-coder-14b-instruct-q4_k_m.gguf \
     https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct-GGUF/resolve/main/qwen2.5-coder-14b-instruct-q4_k_m.gguf
   sha256sum qwen2.5-coder-14b-instruct-q4_k_m.gguf
   ```

   The checksum must be `c1e659736d89ac1065fb495330fb824d94001974a4bfa78e7270e43476a8d940` (the `gguf_checksum` of the `dev` profile in `codecompass.toml`). If it differs, delete the file and download it again.

6. **Make your config file.** The `codecompass` command reads `codecompass.toml` from the repo you ask about, then `~/.config/codecompass/codecompass.toml`. It never reads the project's own copy, so copy it there:

   ```bash
   mkdir -p ~/.config/codecompass
   cp ~/CodeCompass-project/codecompass.toml ~/.config/codecompass/codecompass.toml
   grep -n '^\[embedder\]\|^\[reranker\]' ~/.config/codecompass/codecompass.toml
   ```

   If `grep` prints nothing, add the GPU settings, once only:

   ```bash
   printf '\n[embedder]\ndevice = "cuda"\n\n[reranker]\ndevice = "cuda"\ndtype = "float16"\n' >> ~/.config/codecompass/codecompass.toml
   ```

   If it prints line numbers, those sections already exist. Open the file with `nano` and check they say `device = "cuda"`, plus `dtype = "float16"` under `[reranker]`. Without these settings, the re-ranker runs on the CPU and each question takes minutes instead of seconds.

7. **Save your environment settings** so each session needs one command:

   ```bash
   cat > ~/cc-env.sh <<'EOF'
   module load Python/3.12.8-GCCcore-13.3.0
   source ~/cc-venv/bin/activate
   export LD_LIBRARY_PATH=/opt/apps/software/GCCcore/13.3.0/lib64:$HOME/llama.cpp-src/build/bin:/opt/apps/software/CUDA/12.6.0/lib64:$LD_LIBRARY_PATH
   EOF
   ```

   The first path in `LD_LIBRARY_PATH` supplies the newer C++ library that `llama-server` needs. Without it, the server fails with `GLIBCXX_3.4.32 not found`.

## Every session

After the setup, a session is four steps.

1. Get a 3090 GPU shell (see [Get a 3090 GPU shell](#get-a-3090-gpu-shell) above).

2. Load your settings:

   ```bash
   source ~/cc-env.sh
   cd ~/CodeCompass-project
   ```

3. Start the model server in the background and wait for it. Loading takes a few minutes:

   ```bash
   ~/llama.cpp-src/build/bin/llama-server \
     -m ~/.cache/codecompass/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf \
     --host 127.0.0.1 --port 8080 -c 32768 --jinja -ngl 99 > ~/llama-server.log 2>&1 &
   until curl -sf http://127.0.0.1:8080/health; do sleep 5; done; echo
   ```

   Wait for `{"status":"ok"}`. If the shell prints `Exit 1` instead, press Ctrl-C and read `tail -30 ~/llama-server.log`. `-c 32768` must match the `dev` profile's `context_window`, and `--host 127.0.0.1` keeps the server local to the node (constitution Article VIII.2).

4. Open CodeCompass:

   ```bash
   codecompass ~/repos/flask --profile dev
   ```

   The first lines show the repo, `profile dev (Qwen2.5-Coder-14B-Instruct)` and your config file. No warning about `llama-server` means the model is connected.

## Asking questions and reading answers

Name a specific file or function in every question. Vague questions are blocked by the evidence gate before the model runs, and you get *could not find enough evidence*. For example:

```
What does Flask.test_request_context in src/flask/app.py do?
Use git_log on src/flask/app.py and tell me the most recent commit that changed it.
```

While it works, the model's unchecked draft appears dimmed under a **DRAFT — NOT CHECKED** header. The checked answer then replaces it. On the 3090, an answer takes about 2 to 6 seconds once the index and models have loaded.

- **Commands:** `/tools` lists the tools the last answer used, `/theme none` turns colour off, and `/exit` or Ctrl-D quits.
- **Flags in answers:** `[UNVERIFIED]`, `(not cited)` or a warning banner mean the citation check failed for part of the answer.
- **A clean answer can still be wrong.** The check only confirms that cited lines exist in the code the model was shown. In one test, *Where are the context-local proxy objects request, g and session created?* passed the check but answered from `ctx.py` instead of `globals.py`. Always open the cited lines yourself.

To see what was retrieved for a question, with re-rank scores and which chunks were sent, run a one-off question with `--verbose`. Pass `--config` so it uses your GPU settings:

```bash
python -m codecompass.online.cli ask ~/repos/flask "<question>" \
  --config ~/.config/codecompass/codecompass.toml --verbose
```

## Updating your code

You don't need to restart the server or reinstall to test new code.

1. In CodeCompass, type `/exit`. You stay on the GPU node and the server keeps running.
2. On your laptop, run the same `rsync` command from setup step 1. It copies only changed files, and the GPU node sees them straight away because home folders are shared.
3. On the GPU node, run `codecompass ~/repos/flask --profile dev` again. The editable install picks up the new code.

Two changes need an extra step:

- **`requirements.txt` changed:** run `pip install -r requirements.txt`.
- **Profiles in `codecompass.toml` changed:** redo setup step 6, because CodeCompass reads your copy in `~/.config/codecompass/`, not the project's.

`rsync` never deletes files on the cluster. Add `--delete` only when you want the cluster copy to match your laptop exactly.

## Finishing a session

Free the GPU when you're done, so it's available to others and doesn't use up one of your two job slots.

```bash
/exit      # inside CodeCompass
kill %1    # stops llama-server
exit       # leaves the GPU node and ends the job
```

If your connection drops, the job can stay listed. Run `myqueue` on `origami` and `scancel <jobid>` to end it.

## Troubleshooting

Every error below came up while setting this up on 7 November 2026.

| What you see | Cause | Fix |
|---|---|---|
| `ssh` or `rsync` times out while connecting | The cluster's hostname resolves to an on-campus address | Connect to the VPN address instead of the hostname |
| `srun: error: Unable to create step ... Memory required by task is not available` | Leftover `SLURM_JOB_ID` in your login shell | `unset $(env \| grep -o '^SLURM_[A-Z_]*')`, or log in again |
| `nvidia-smi` shows a GTX 1080 Ti or RTX 2080 | No GPU type was requested | `exit` and rerun `srun` with `--constraint=3090` |
| Server prints `Exit 1`; log says `GLIBCXX_3.4.32 not found` | System C++ library is too old | `source ~/cc-env.sh`, then start the server again |
| `No module named 'git'` from `/usr/lib64/python3.9` | System Python, not your venv | `source ~/cc-env.sh` |
| `python -m codecompass.online.tui` returns with no output | That module has no `__main__` entry point | Use the `codecompass` command |
| `Cannot declare ('embedder',) twice` | GPU settings appended twice to the config | Redo setup step 6 from the `cp` line |
| *could not find enough evidence* | Question too vague for the evidence gate | Name a file or function |
| Each question takes minutes | Re-ranker on the CPU | Check `device = "cuda"` in `~/.config/codecompass/codecompass.toml` |

Results from this setup are development signals only. Reported evaluation results follow constitution Article VII and the rules in `AGENTS.md` (never index or query `fastapi/fastapi`).
