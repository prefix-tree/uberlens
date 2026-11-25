#!/usr/bin/env bash
# Prepares the interview film's media into ./media, from public sources, with the lab's own modules. It needs
# ffmpeg, git, curl and Python with numpy, torch and torchvision, and about 2 GB of disk while it runs. It skips
# what is already there. Run it from the repository's root:
#
#   bash uberseek/lab/interview/prepare.sh
#
# What it fetches: 42 seconds of a NASA interview and its b-roll (public domain), Kenney's interface sounds (CC0, from
# the soundcn repository), and RobustVideoMatting with its weights (GPL-3.0; used to make the cut-out, not shipped).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
media="$here/media"; work="$here/.work"
mkdir -p "$media" "$work"
py=${PYTHON:-python3}
SVS=https://svs.gsfc.nasa.gov/vis/a010000/a015100/a015111
FPS=24000/1001
VP9="-c:v libvpx-vp9 -g 24 -deadline good -cpu-used 4 -row-mt 1 -pix_fmt yuv420p"

# 1. The answer, 3:02 to 3:42 of the interview: only those seconds of a 12.8 GB file.
[ -f "$work/talk.mov" ] || $py -m uberseek.lab.fetch "$SVS/JOE_WESTLAKE.mov" 182 222 "$work/talk.mov"

# 2. The clip the film plays: 36.6 s, its speech brought to -14 LUFS (an editor's export may have no limiter).
[ -f "$media/talk.webm" ] || ffmpeg -v error -y -t 36.6 -i "$work/talk.mov" -af "loudnorm=I=-14:TP=-2:LRA=9" -ar 48000 \
  $VP9 -b:v 6M -c:a libopus -b:a 160k "$media/talk.webm"

# 3. The cut-out: the same frames with the speaker over pure green.
if [ ! -f "$media/cutout.webm" ]; then
  [ -d "$work/rvm" ] || git clone -q --depth 1 https://github.com/PeterL1n/RobustVideoMatting.git "$work/rvm"
  [ -f "$work/rvm_resnet50.pth" ] || curl -sL -o "$work/rvm_resnet50.pth" \
    https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50.pth
  $py -m uberseek.lab.matte "$work/talk.mov" "$media/cutout.webm" --rvm "$work/rvm" --weights "$work/rvm_resnet50.pth" --seconds 36.6
fi

# 4. The b-roll: the spacecraft and Saturn, from the interview's b-roll reel.
[ -f "$work/broll.webm" ] || curl -s -o "$work/broll.webm" "$SVS/VOYAGER_1_BROLL_NEW_1.webm"
[ -f "$media/voyager.webm" ] || ffmpeg -v error -y -ss 18.8 -t 4.2 -i "$work/broll.webm" -r $FPS $VP9 -b:v 4M -an "$media/voyager.webm"
[ -f "$media/saturn.webm" ] || ffmpeg -v error -y -ss 113 -t 5 -i "$work/broll.webm" -r $FPS $VP9 -b:v 3M -an "$media/saturn.webm"

# 5. The cards: a full frame of white, and of the film's blue.
[ -f "$media/white.png" ] || ffmpeg -v error -y -f lavfi -i "color=c=white:s=1920x1080" -frames:v 1 "$media/white.png"
[ -f "$media/blue.png" ] || ffmpeg -v error -y -f lavfi -i "color=c=0x0d2cf5:s=1920x1080" -frames:v 1 "$media/blue.png"

# 6. The sounds: the music is synthesized; the key clicks come from Kenney's interface sounds.
if [ ! -f "$media/music.wav" ]; then
  [ -d "$work/soundcn" ] || git clone -q --depth 1 https://github.com/kapishdima/soundcn.git "$work/soundcn"
  $py -m uberseek.lab.sounds "$work/soundcn/assets/kenney_interface-sounds" "$media"
fi

echo "media is in $media"
