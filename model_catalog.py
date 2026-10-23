from pathlib import Path
ROOT=Path(__file__).resolve().parent
WEIGHTS=ROOT/'weights'
HF_MODELS={
 'signature':{'repo':'NethranjaliSE/resnet34-signature-verification','revision':'8d930d0dcc4ff86121cbfd88c0f710a1fb7d2b8f','files':['model.pt','README.md']},
 'video':{'repo':'dima806/deepfake_vs_real_image_detection','revision':'29e4cf9efc543845610045f6ba7e88e5cf9d9301','files':['config.json','preprocessor_config.json','model.safetensors','README.md']},
 'audio':{'repo':'MelodyMachine/Deepfake-audio-detection','revision':'8fa126974c64f5ba601484de0446ddf1839f58f9','files':['config.json','preprocessor_config.json','model.safetensors','README.md']},
 'speaker':{'repo':'microsoft/wavlm-base-plus-sv','revision':'feb593a6c23c1cc3d9510425c29b0a14d2b07b1e','files':['config.json','preprocessor_config.json','pytorch_model.bin','README.md']},
}
FACE_FILES={
 'yunet.onnx':'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
 'sface.onnx':'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx',
}

# SHA256 of the pinned, downloaded assets verified during the build.
FILE_HASHES={'signature/model.pt': '7e9ff3f9ac650c707b7a8014f4401a7d577dfc0c56e0ddae87b4a139a347abae', 'signature/README.md': 'e05cf295a3001b598dc18bfafde7f6a66a51f8a3ae5d90706010875b6b268d92', 'video/config.json': '11bf93504ca2fed8f285127f407b235739873a85d4ec182939a6f8faebb62d3d', 'video/preprocessor_config.json': 'a34861a24e781942424ad790b82bc99348404a2e64ea882de88c40905851698d', 'video/model.safetensors': 'b38e7d3de2be44b224cb4cffe881a0c4b75f7283c5d4a2017fbadd58bd41fdef', 'video/README.md': 'd0c0726bee490677ed340a8be6fdcdc1605fddd4bd938dc91f6112775f06c862', 'audio/config.json': '8c7543d6ee27abbf8d6a91881fa0aea2672a4b076ecc94f1ce8f7ccbf800a9c6', 'audio/preprocessor_config.json': '8cdfd65ff4115423185a1512bdae100e2e0cd744f5b322417429944aaafd0827', 'audio/model.safetensors': 'c71b6b61f2d7328585256b42b6b65c6e8b9f1c35712fc0fefea61bbafc7d478d', 'audio/README.md': '5cd88b16c8b27f72ab7faa09d18e9fd85093cbdd9857ca2f67c7424159d541b3', 'speaker/config.json': 'c6ac8c0ce55b18d4612677931036fe5ce78093e87361c552a173f00a0bb07514', 'speaker/preprocessor_config.json': '99272fe8ccfab114b68b478681ea47ee3a1ce62bb788cb92dd6e4f69fb1f1da2', 'speaker/pytorch_model.bin': 'e906bce2fa42fb497a1d1a9ecf81548adb7e03b12a5644e32d2f42f0d6500fad', 'speaker/README.md': '97f5513cde351b3adb4e182b60ec23154dadba7ca83e667ceace237177855b8e', 'face/yunet.onnx': '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4', 'face/sface.onnx': '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'}
