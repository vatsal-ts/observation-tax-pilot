# Remaining experiment queue, run sequentially in one detached process.
#
# Sequential on purpose: several 10-worker jobs at once would fight over the
# rate limit for no wall-clock gain. Each run appends to its own log under
# runs/ so progress survives this window, the terminal, and the Claude session.

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
"queue started $stamp" | Out-File -FilePath "runs\queue_status.log" -Encoding utf8

function Run-Grid {
    param([string]$Tag, [string[]]$ExtraArgs)
    $started = Get-Date -Format "HH:mm:ss"
    "[$started] START $Tag" | Out-File -FilePath "runs\queue_status.log" -Append -Encoding utf8
    $args = @("-u", "run_grid.py", "--episodes", "50", "--workers", "10",
              "--max-turns", "120") + $ExtraArgs
    & python $args *> "runs\grid_$Tag.log"
    $done = Get-Date -Format "HH:mm:ss"
    "[$done] DONE  $Tag (exit $LASTEXITCODE)" |
        Out-File -FilePath "runs\queue_status.log" -Append -Encoding utf8
}

# 1. Does stating the cost more loudly change anything?
Run-Grid "52_salient"  @("--model","gpt-5.2","--prompt-style","salient")

# 2. Predictability control: an effect confined to inferable schedules is
#    failed extrapolation, not failed grounding.
Run-Grid "52_periodic" @("--model","gpt-5.2","--schedule","periodic")

# 3. Matched control family: the target never moves, so cost should not bite.
Run-Grid "52_static"   @("--model","gpt-5.2","--family","static-target")

# 4. Capability axis. All three cleared the T=0 gate.
Run-Grid "41_plain"    @("--model","gpt-4.1")
Run-Grid "4omini_plain" @("--model","gpt-4o-mini")
Run-Grid "35turbo_plain" @("--model","gpt-3.5-turbo")

"[$(Get-Date -Format 'HH:mm:ss')] QUEUE COMPLETE" |
    Out-File -FilePath "runs\queue_status.log" -Append -Encoding utf8
