from pathlib import Path
import logging
import random

import joblib

try:
    from sklearn.linear_model import LinearRegression
except ImportError as exc:  # pragma: no cover - friendly runtime guidance
    raise ImportError(
        "scikit-learn is required to train CreatorMind AI. "
        "Install backend requirements, then run: python -m backend.models.train_model"
    ) from exc


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent
MODEL_PATH = MODEL_DIR / "model.pkl"

FEATURE_COLUMNS = [
    "platform",
    "contentType",
    "captionLength",
    "hashtagsCount",
    "postingHour",
]

CATEGORY_MAPS = {
    "platform": {
        "Instagram": 0,
        "TikTok": 1,
        "YouTube": 2,
        "__unknown__": 0,
    },
    "contentType": {
        "Post": 0,
        "Story": 1,
        "Reel": 2,
        "Short": 3,
        "__unknown__": 0,
    },
}


def build_training_rows() -> tuple[list[list[float]], list[float]]:
    random.seed(42)
    rows: list[list[float]] = []
    targets: list[float] = []

    for platform, platform_code in CATEGORY_MAPS["platform"].items():
        if platform == "__unknown__":
            continue

        for content_type, content_code in CATEGORY_MAPS["contentType"].items():
            if content_type == "__unknown__":
                continue

            for caption_length in [30, 60, 100, 150, 220]:
                for hashtags_count in [0, 3, 6, 10]:
                    for posting_hour in [9, 13, 18, 21]:
                        short_form_bonus = 1800 if content_type in {"Reel", "Short"} else 400
                        platform_bonus = {"Instagram": 900, "TikTok": 1300, "YouTube": 700}[platform]
                        timing_bonus = 2200 if 17 <= posting_hour <= 21 else 700
                        hashtag_bonus = hashtags_count * 250
                        caption_bonus = caption_length * 16
                        noise = random.randint(-250, 250)

                        target_views = max(
                            500,
                            1200
                            + short_form_bonus
                            + platform_bonus
                            + timing_bonus
                            + hashtag_bonus
                            + caption_bonus
                            + noise,
                        )

                        rows.append(
                            [
                                float(platform_code),
                                float(content_code),
                                float(caption_length),
                                float(hashtags_count),
                                float(posting_hour),
                            ]
                        )
                        targets.append(float(target_views))

    return rows, targets


def train_and_save_model() -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    x_train, y_train = build_training_rows()
    model = LinearRegression()
    model.fit(x_train, y_train)

    bundle = {
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "category_maps": CATEGORY_MAPS,
        "metadata": {
            "artifact_type": "model_bundle",
            "model_name": "LinearRegression",
            "target": "views",
        },
    }

    joblib.dump(bundle, MODEL_PATH)

    logger.info("Saved model bundle to %s", MODEL_PATH)
    logger.info("Saved object type: %s", type(bundle).__name__)
    return MODEL_PATH


if __name__ == "__main__":
    train_and_save_model()
