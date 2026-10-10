# M0 environment discovery
Recorded: 2026-10-10. These are **hosted implementation-runner facts**, not
the repository owner's Windows laptop specifications.

| Item | Observed |
| --- | --- |
| OS / architecture | Linux 6.18.44 x86-64 |
| Shell | Bash (`/bin/bash`) |
| Python | 3.13.5 |
| uv / pip | uv 0.10.0 / pip 25.1.1 |
| GPU and CUDA | No accessible GPU; CUDA unavailable |
| RAM | 5.8 GiB total |
| Free disk | Approximately 30 GiB |
| Direct outbound internet | Unavailable (DNS lookup failed) |
| GitHub repository access | Available via authenticated GitHub connector |
| Docker | No `docker` executable |
| ffmpeg | 7.1.5 |
| git | 2.47.3; global author identity not configured |

## Implications
Default provider is offline cassette, tests never require a GPU or network,
and a tiny smoke benchmark can run entirely on CPU. Heavy future model
evaluations must document separate cloud execution instructions, hardware,
price source and actual spend. Re-run this discovery on the user's laptop.

CI runs on a **different** GitHub Actions hosted Ubuntu environment, with
Python 3.11 and 3.12. The fingerprint microbenchmark records the runtime,
package versions and commit of the actual machine performing a measurement.
