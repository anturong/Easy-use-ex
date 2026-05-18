from .AdvancedImageResizer import ImageResizeWithColorAndDirection
from .BatchRoleSplitSRT import EasyUseSplitSrtByRole
from .ColorID2Mask import (
    ColorID2Mask,
    ColorID2MaskBatch,
)
from .EasyUseDubbingAutomation import EasyUseDubbingAutomation
from .EasyUseImageSave import EasyUseImageSave
from .EasyUseLoadAudioBatch import EasyUseLoadAudioBatch
from .EasyUseLoadImageBatch import EasyUseLoadImageBatch
from .EasyUseLoadSrtBatch import EasyUseLoadSrtBatch
from .EasyUseLoadTxtBatch import EasyUseLoadTxtBatch
from .EasyUseSaveAudioBatch import EasyUseSaveAudioBatch
from .EasyUseSaveSrtBatch import EasyUseSaveSrtBatch
from .EasyUseSaveTxtBatch import EasyUseSaveTxtBatch
from .EasyUseSubCastEditor import EasyUseSubCastEditor
from .Qwen3ApiAudioToSRT import (
    EasyUseQwen3ASR,
    EasyUseQwen3ForcedAlignerLoader,
    EasyUseQwen3ForcedAlign,
)
from .Qwen3AutoAlignedSRT import EasyUseRoleAlignedSRT


NODE_CLASS_MAPPINGS = {
    "Easy Use Load Image Batch": EasyUseLoadImageBatch,
    "Easy Use Image Save": EasyUseImageSave,
    "Easy Use Load Audio Batch": EasyUseLoadAudioBatch,
    "Easy Use Save Audio Batch": EasyUseSaveAudioBatch,
    "Easy Use Load Srt Batch": EasyUseLoadSrtBatch,
    "Easy Use Save Srt Batch": EasyUseSaveSrtBatch,
    "Easy Use Load Txt Batch": EasyUseLoadTxtBatch,
    "Easy Use Save Txt Batch": EasyUseSaveTxtBatch,
    "Easy Use SubCast Editor": EasyUseSubCastEditor,
    "Easy Use Role Aligned SRT": EasyUseRoleAlignedSRT,
    "Easy Use Split SRT By Role": EasyUseSplitSrtByRole,
    "Easy Use Dubbing Automation": EasyUseDubbingAutomation,
    "ColorID2Mask": ColorID2Mask,
    "ColorID2MaskBatch": ColorID2MaskBatch,
    "ImageResizeWithColorAndDirection": ImageResizeWithColorAndDirection,
    "EasyUseQwen3ASR": EasyUseQwen3ASR,
    "EasyUseQwen3ForcedAlignerLoader": EasyUseQwen3ForcedAlignerLoader,
    "EasyUseQwen3ForcedAlign": EasyUseQwen3ForcedAlign,
}


NODE_DISPLAY_NAME_MAPPINGS = {
    "Easy Use Load Image Batch": "批量加载图像",
    "Easy Use Image Save": "批量保存图像",
    "Easy Use Load Audio Batch": "批量加载音频",
    "Easy Use Save Audio Batch": "批量保存音频",
    "Easy Use Load Srt Batch": "批量加载 SRT",
    "Easy Use Save Srt Batch": "批量保存 SRT",
    "Easy Use Load Txt Batch": "批量加载 TXT",
    "Easy Use Save Txt Batch": "批量保存 TXT",
    "Easy Use Role Aligned SRT": "Qwen3 API 音频 to SRT",
    "Easy Use Split SRT By Role": "批量角色分割SRT",
    "Easy Use Dubbing Automation": "配音自动化",
    "ColorID2Mask": "ColorID 转遮罩",
    "ColorID2MaskBatch": "ColorID 批量转遮罩",
    "ImageResizeWithColorAndDirection": "高级画布调整",
    "EasyUseQwen3ASR": "Qwen3 语音识别",
    "EasyUseQwen3ForcedAlignerLoader": "Qwen3 强制对齐器加载",
    "EasyUseQwen3ForcedAlign": "Qwen3 文本音频对齐",
    "Easy Use SubCast Editor": "字幕编辑器",
}


WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
