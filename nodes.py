import os
import torchaudio
import numpy as np
import glob
import torch
import torchaudio
from einops import rearrange
from stable_audio_tools import get_pretrained_model
from stable_audio_tools.inference.generation import generate_diffusion_cond
from safetensors.torch import load_file
from .util_config import get_model_config
from stable_audio_tools.models.factory import create_model_from_config
from stable_audio_tools.models.utils import load_ckpt_state_dict

device = "cuda" if torch.cuda.is_available() else "cpu"

base_path = os.path.dirname(os.path.realpath(__file__))
os.makedirs("models/audio_checkpoints", exist_ok=True)

model_files = [os.path.basename(file) for file in glob.glob("models/audio_checkpoints/*.safetensors")] + [os.path.basename(file) for file in glob.glob("models/audio_checkpoints/*.ckpt")]
if len(model_files) == 0:
    model_files.append("Put models in models/audio_checkpoints")



class ModelLoader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model_filename": (model_files, )
            }
        }

    RETURN_TYPES = ("MODEL", )
    FUNCTION = "load_model"
    OUTPUT_NODE = True

    CATEGORY = "audio"

    def load_model(self, model_filename):
        model_path = f"models/audio_checkpoints/{model_filename}"
        if model_filename.endswith(".safetensors") or model_filename.endswith(".ckpt"):
            model_config = get_model_config()
            model = create_model_from_config(model_config)
            model.load_state_dict(load_ckpt_state_dict(model_path))
        else:
            model, model_config = get_pretrained_model("stabilityai/stable-audio-open-1.0")
        
        model = model.to(device)
        return model, model_config

class AudioSampler:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL", ),
                "prompt": ("STRING", {"default": "128 BPM tech house drum loop"}),
                "steps": ("INT", {"default": 100, "min": 1, "max": 10000}),
                "cfg_scale": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sample_size": ("INT", {"default": 65536, "min": 1, "max": 1000000}),
                "sigma_min": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 1000.0, "step": 0.01}),
                "sigma_max": ("FLOAT", {"default": 500.0, "min": 0.0, "max": 1000.0, "step": 0.01}),
                "sampler_type": ("STRING", {"default": "dpmpp-3m-sde"}),
                "save": ("BOOLEAN", {"default": True}),
                "save_path": ("STRING", {"default": "output.wav"}),
            }
        }

    RETURN_TYPES = ("audio_bytes", "sample_rate")
    FUNCTION = "generate_audio"
    OUTPUT_NODE = True

    CATEGORY = "audio"

    def generate_audio(self, model, prompt, steps, cfg_scale, sample_size, sigma_min, sigma_max, sampler_type, save, save_path):
        conditioning = [{
            "prompt": prompt,
            "seconds_start": 0,
            "seconds_total": 30
        }]
        
        seed = np.random.randint(0, np.iinfo(np.int32).max)

        output = generate_diffusion_cond(
            model,
            steps=steps,
            cfg_scale=cfg_scale,
            conditioning=conditioning,
            sample_size=sample_size,
            sigma_min=sigma_min,
            sigma_max=sigma_max,
            sampler_type=sampler_type,
            device=device,
            seed=seed,
        )

        output = rearrange(output, "b d n -> d (b n)")

        output = output.to(torch.float32).div(torch.max(torch.abs(output))).clamp(-1, 1).mul(32767).to(torch.int16).cpu()
        
        if save:
            torchaudio.save("output/" + save_path, output, model.sample_rate)
        
        # Convert to bytes
        audio_bytes = output.numpy().tobytes()
        
        return audio_bytes, model.sample_rate

class AudioPlayer:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "audio_bytes": ("audio_bytes", ),
                "sample_rate": ("sample_rate", )
            }
        }

    RETURN_TYPES = ("HTML", )
    FUNCTION = "play_audio"
    OUTPUT_NODE = True

    CATEGORY = "audio"

    def play_audio(self, audio_bytes, sample_rate):
        # Save audio to a temporary file
        temp_path = "output/temp_audio.wav"
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        # HTML content for audio playback
        html_content = f"""
        <audio controls>
            <source src="{temp_path}" type="audio/wav">
            Your browser does not support the audio element.
        </audio>
        """
        return html_content

NODE_CLASS_MAPPINGS = {
    "ModelLoader": ModelLoader,
    "AudioSampler": AudioSampler,
    "AudioPlayer": AudioPlayer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelLoader": "Load Stable Diffusion Audio Model",
    "AudioSampler": "Generate Audio with Stable Diffusion",
    "AudioPlayer": "Audio Player",
}
