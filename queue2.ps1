# Powered follow-ups, run sequentially in one detached process.
#
# Two questions the n=50 runs left open:
#
#  1. Is the response economic or informational? The 2x2 of charged budget
#     against drift, at a fixed stated price, so no instruction is in play.
#     200 episodes per cell.
#
#  2. Does the original interaction survive? The stated-price effect at
#     charged 0 versus charged 5, in the original coupled design, at 200
#     episodes per cell. At n=50 its CI was [-14.50, +0.46] and included zero.

$ErrorActionPreference = "Continue"
Set-Location "C:\Users\vgupt\OneDrive\Desktop\Vatsal\L3\pilot"
"queue2 started $(Get-Date -Format 'HH:mm:ss')" |
    Out-File -FilePath "runs\queue2_status.log" -Encoding utf8

function Run-Step {
    param([string]$Tag, [string[]]$Cmd)
    "[$(Get-Date -Format 'HH:mm:ss')] START $Tag" |
        Out-File -FilePath "runs\queue2_status.log" -Append -Encoding utf8
    & python $Cmd *> "runs\$Tag.log"
    "[$(Get-Date -Format 'HH:mm:ss')] DONE  $Tag (exit $LASTEXITCODE)" |
        Out-File -FilePath "runs\queue2_status.log" -Append -Encoding utf8
}

# 1. economic vs informational, powered, no instruction in play
Run-Step "powered_decoupled" @("-u","run_factorial.py","--model","gpt-5.2",
    "--episodes","200","--workers","10","--stated","0")

# 2. the original interaction, powered
Run-Step "powered_interaction" @("-u","run_grid.py","--model","gpt-5.2",
    "--episodes","200","--workers","10","--max-turns","120","--costs","0","5")

"[$(Get-Date -Format 'HH:mm:ss')] QUEUE2 COMPLETE" |
    Out-File -FilePath "runs\queue2_status.log" -Append -Encoding utf8
