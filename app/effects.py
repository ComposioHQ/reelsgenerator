from PIL import Image

from pkg_resources import parse_version

from PIL import Image as pil

if parse_version(pil.__version__) >= parse_version("10.0.0"):
    Image.ANTIALIAS = Image.LANCZOS  # type: ignore


def zoom_in_effect(clip, duration=2.0, fps=30):
    return clip.filter(
        "zoompan",
        z="1+(0.05*in/24)",
        d=1,
    )


def zoom_out_effect(clip, duration=2.0, fps=30):
    effect = clip.filter(
        "zoompan",
        z="if(between(in,0,450),1+(0.05*in/24),min(max(zoom,pzoom)-0.050,5.0))",
        x="320.0*4.0-(320.0*4.0/zoom)",
        y="240.0*4.0-(240.0*4.0/zoom)",
        d=1,
    )

    return effect