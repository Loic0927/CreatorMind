import { useRef, useState } from "react";
import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import { AiConsentModal } from "../components/AiConsentModal";
import { UnifiedPicker } from "../components/UnifiedPicker";
import { Button } from "../components/ui";
import { getAIProcessingConsent, grantAIProcessingConsent, publishPost } from "../services/api";
import { CaptionGenerationError, generateCaption } from "../services/caption";
import { CAPTION_MODE } from "../config/environment";
import { Draft, InstagramConnection, MediaMimeType } from "../types";
import { colors } from "../theme/colors";

const GOALS = [
  "Grow engagement",
  "Educate",
  "Build trust",
  "Increase brand awareness",
  "Share an announcement",
  "Other",
];
const GOAL_OPTIONS = GOALS.map((value) => ({ value, label: value }));
const HASHTAG_OPTIONS = Array.from({ length: 11 }, (_, value) => ({ value: String(value), label: String(value) }));
const SUPPORTED_VIDEO_TYPES: MediaMimeType[] = ["video/mp4", "video/quicktime"];
const MAX_MEDIA_BYTES = 7 * 1024 * 1024;
const MAX_VIDEO_DURATION_SECONDS = 60;

function base64ByteLength(value: string): number {
  const padding = value.endsWith("==") ? 2 : value.endsWith("=") ? 1 : 0;
  return Math.floor((value.length * 3) / 4) - padding;
}

type Props = {
  draft: Draft;
  setDraft: (value: Draft) => void;
  connection: InstagramConnection | null;
  accessToken: string;
};

export function CreateScreen({ draft, setDraft, connection, accessToken }: Props) {
  const scroll = useRef<ScrollView>(null);
  const [generating, setGenerating] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [consentModalVisible, setConsentModalVisible] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);

  const pick = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images", "videos"],
      allowsEditing: true,
      quality: 0.9,
      base64: true,
    });
    if (result.canceled) return;

    const asset = result.assets[0];
    const mediaKind = asset.type === "video" ? "video" : "image";
    if (mediaKind === "image") {
      try {
        const context = ImageManipulator.manipulate(asset.uri);
        const rendered = await context.renderAsync();
        const converted = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: 0.92, base64: true });
        if (!converted.base64) throw new Error("JPEG conversion returned no image data.");
        if (base64ByteLength(converted.base64) > MAX_MEDIA_BYTES) {
          Alert.alert("Image too large", "The converted JPEG must be smaller than 7 MB.");
          return;
        }
        setDraft({
          ...draft,
          imageUri: converted.uri,
          imageData: converted.base64,
          imageMimeType: "image/jpeg",
          mediaKind: "image",
          mediaDurationSeconds: undefined,
          hasResults: false,
        });
      } catch (error) {
        Alert.alert("Image conversion failed", error instanceof Error ? error.message : "Choose another image file.");
      }
      return;
    }

    const mimeType = asset.mimeType as MediaMimeType | undefined;
    if (!mimeType || !SUPPORTED_VIDEO_TYPES.includes(mimeType)) {
      Alert.alert("Unsupported video", "Choose an MP4 or MOV video.");
      return;
    }
    if (asset.fileSize && asset.fileSize > MAX_MEDIA_BYTES) {
      Alert.alert("Video too large", "Choose a video smaller than 7 MB.");
      return;
    }
    const durationSeconds = asset.duration == null ? undefined : asset.duration / 1000;
    if (durationSeconds == null || durationSeconds > MAX_VIDEO_DURATION_SECONDS) {
      Alert.alert("Video too long", "Choose a video that is one minute or shorter.");
      return;
    }
    const mediaData =
      asset.base64 || (await FileSystem.readAsStringAsync(asset.uri, { encoding: FileSystem.EncodingType.Base64 }));
    setDraft({
      ...draft,
      imageUri: asset.uri,
      imageData: mediaData,
      imageMimeType: mimeType,
      mediaKind: "video",
      mediaDurationSeconds: durationSeconds,
      hasResults: false,
    });
  };

  const removeMedia = () =>
    setDraft({
      ...draft,
      imageUri: undefined,
      imageData: undefined,
      imageMimeType: undefined,
      mediaKind: undefined,
      mediaDurationSeconds: undefined,
      hasResults: false,
    });

  const generate = async () => {
    setGenerating(true);
    try {
      const result = await generateCaption(
        {
          information: draft.information,
          goal: draft.goal === "Other" ? draft.otherGoal.trim() : draft.goal,
          platform: "Instagram",
          platforms: ["Instagram"],
          hashtag_count: draft.hashtagCount,
          use_account_context: draft.useAccountContext,
          media:
            draft.imageData && draft.imageMimeType
              ? {
                  mime_type: draft.imageMimeType,
                  data: draft.imageData,
                  duration_seconds: draft.mediaDurationSeconds,
                }
              : undefined,
        },
        accessToken,
      );
      setDraft({ ...draft, ...result, platform: "Instagram", platforms: ["Instagram"], hasResults: true });
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
    } catch (error) {
      if (error instanceof CaptionGenerationError && error.code === "consent_required") {
        setConsentModalVisible(true);
        return;
      }
      Alert.alert("Generation failed", error instanceof Error ? error.message : "Try again.");
    } finally {
      setGenerating(false);
    }
  };

  const create = async () => {
    if (!draft.information.trim() && !draft.imageData) return Alert.alert("Add information or choose media");
    if (!draft.goal || (draft.goal === "Other" && !draft.otherGoal.trim())) return Alert.alert("Choose a goal");
    if (CAPTION_MODE === "api") {
      try {
        if (!(await getAIProcessingConsent(accessToken)).ai_processing_consented) {
          setConsentModalVisible(true);
          return;
        }
      } catch (error) {
        Alert.alert("AI processing", error instanceof Error ? error.message : "Could not check AI processing consent.");
        return;
      }
    }
    await generate();
  };

  const acceptConsent = async () => {
    setSavingConsent(true);
    try {
      await grantAIProcessingConsent(accessToken);
      setConsentModalVisible(false);
      await generate();
    } catch (error) {
      Alert.alert("AI processing", error instanceof Error ? error.message : "Could not save AI processing consent.");
    } finally {
      setSavingConsent(false);
    }
  };

  const publish = async () => {
    if (!connection?.connected)
      return Alert.alert("Connect Instagram", "Connect your Instagram account in Settings before publishing.");
    if (!draft.imageData || !draft.imageMimeType)
      return Alert.alert("Media required", "Choose an image or short video before publishing.");

    setPublishing(true);
    try {
      const { results } = await publishPost(accessToken, {
        platforms: ["Instagram"],
        caption: draft.caption,
        hashtags: draft.hashtags,
        media: {
          mime_type: draft.imageMimeType,
          data: draft.imageData,
          duration_seconds: draft.mediaDurationSeconds,
        },
      });
      const result = results.find((item) => item.platform === "Instagram") ?? results[0];
      Alert.alert(
        result?.status === "published" ? "Published to Instagram" : "Publishing failed",
        result?.message || "Instagram did not return a publication result.",
      );
    } catch (error) {
      Alert.alert("Publishing failed", error instanceof Error ? error.message : "Try again.");
    } finally {
      setPublishing(false);
    }
  };

  const canPublish = Boolean(connection?.connected && draft.imageData && draft.imageMimeType);
  const selectedMediaLabel =
    draft.mediaKind === "video"
      ? `Video selected · ${Math.ceil(draft.mediaDurationSeconds ?? 0)}s`
      : draft.imageMimeType === "image/jpeg"
        ? "JPEG image selected"
        : "Image selected · converts to JPEG when published";

  return (
    <>
      <ScrollView
        ref={scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
      >
        <Text style={styles.title}>Create post</Text>

        <View style={styles.card}>
          <View style={styles.field}>
            <Text style={styles.label}>Social platform</Text>
            <View style={styles.platformField}>
              <View style={styles.platformChip}>
                <Text style={styles.platformText}>Instagram</Text>
              </View>
            </View>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>Content</Text>
            {draft.imageUri ? (
              <View style={styles.mediaBox}>
                {draft.mediaKind === "video" ? (
                  <View style={styles.videoPlaceholder}>
                    <Text style={styles.playIcon}>▶</Text>
                    <Text style={styles.videoText}>Short video ready</Text>
                  </View>
                ) : (
                  <Image source={{ uri: draft.imageUri }} style={styles.image} />
                )}
              </View>
            ) : (
              <Pressable accessibilityRole="button" onPress={pick} style={styles.choose}>
                <Text style={styles.uploadIcon}>+</Text>
                <Text style={styles.chooseText}>Choose an image or short video</Text>
                <Text style={styles.chooseHelp}>JPG, PNG, WebP, MP4 or MOV · video up to 60s · up to 7 MB</Text>
              </Pressable>
            )}
            {draft.imageUri ? (
              <View style={styles.mediaActions}>
                <Text style={styles.mediaMeta}>{selectedMediaLabel}</Text>
                <Pressable onPress={pick}>
                  <Text style={styles.actionText}>Change</Text>
                </Pressable>
                <Pressable onPress={removeMedia}>
                  <Text style={styles.actionText}>Remove</Text>
                </Pressable>
              </View>
            ) : null}
          </View>

          <Field
            label="Information"
            value={draft.information}
            onChangeText={(information) => setDraft({ ...draft, information, hasResults: false })}
            placeholder="Describe your content, audience and key message"
            multiline
          />
          <UnifiedPicker
            label="Hashtag count"
            options={HASHTAG_OPTIONS}
            value={String(draft.hashtagCount)}
            onChange={(value) => setDraft({ ...draft, hashtagCount: Number(value), hasResults: false })}
          />
          <UnifiedPicker
            label="Goal"
            options={GOAL_OPTIONS}
            value={draft.goal}
            onChange={(goal) =>
              setDraft({ ...draft, goal, otherGoal: goal === "Other" ? draft.otherGoal : "", hasResults: false })
            }
            otherOptionValue="Other"
            otherValue={draft.otherGoal}
            onOtherValueChange={(otherGoal) =>
              setDraft({ ...draft, otherGoal: otherGoal.slice(0, 200), hasResults: false })
            }
            otherPlaceholder="Describe your goal"
          />

          <Pressable
            accessibilityRole="checkbox"
            accessibilityState={{ checked: draft.useAccountContext }}
            onPress={() => setDraft({ ...draft, useAccountContext: !draft.useAccountContext, hasResults: false })}
            style={styles.contextRow}
          >
            <View style={[styles.checkbox, draft.useAccountContext && styles.checkboxChecked]}>
              {draft.useAccountContext ? <Text style={styles.check}>✓</Text> : null}
            </View>
            <Text style={styles.contextText}>Use account context</Text>
          </Pressable>
          <Button label={generating ? "Creating…" : "Create caption"} onPress={create} disabled={generating} />
        </View>

        {draft.hasResults ? (
          <View style={styles.resultCard}>
            <View style={styles.brandRow}>
              <View style={styles.brandIcon}>
                <Text style={styles.brandLetters}>PB</Text>
              </View>
              <View>
                <Text style={styles.brandName}>PostBridge</Text>
                {connection?.username ? <Text style={styles.brandAccount}>@{connection.username}</Text> : null}
              </View>
            </View>
            <Field
              label="Caption"
              value={draft.caption}
              onChangeText={(caption) => setDraft({ ...draft, caption })}
              placeholder="Caption"
              multiline
              tinted
            />
            <Field
              label="Hashtags"
              value={draft.hashtags}
              onChangeText={(hashtags) => setDraft({ ...draft, hashtags })}
              placeholder="#postbridge"
              multiline
              tinted
              hashtag
            />
            {!connection?.connected ? (
              <Text style={styles.publishNote}>Connect Instagram in Settings before publishing.</Text>
            ) : !draft.imageData ? (
              <Text style={styles.publishNote}>Choose an image or short video before publishing.</Text>
            ) : null}
            <Button
              label={
                publishing
                  ? draft.mediaKind === "video"
                    ? "Processing video…"
                    : "Publishing…"
                  : "Publish to Instagram"
              }
              onPress={publish}
              disabled={publishing || !canPublish}
            />
            <Text style={styles.directNote}>
              {draft.mediaKind === "video"
                ? "Short videos publish as Instagram Reels. Processing can take up to about two minutes."
                : "PNG and WebP images are converted to JPEG automatically before publishing."}
            </Text>
          </View>
        ) : null}
      </ScrollView>
      <AiConsentModal
        visible={consentModalVisible}
        busy={savingConsent}
        onAccept={acceptConsent}
        onNotNow={() => setConsentModalVisible(false)}
      />
    </>
  );
}

function Field({
  label,
  value,
  onChangeText,
  placeholder,
  multiline,
  maxLength,
  tinted,
  hashtag,
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder: string;
  multiline?: boolean;
  maxLength?: number;
  tinted?: boolean;
  hashtag?: boolean;
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        maxLength={maxLength}
        multiline={multiline}
        style={[
          styles.input,
          multiline && styles.textarea,
          tinted && styles.tintedInput,
          hashtag && styles.hashtagInput,
        ]}
        textAlignVertical="top"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 36, gap: 16 },
  title: { fontSize: 30, lineHeight: 36, fontWeight: "800", color: colors.ink },
  card: {
    gap: 16,
    padding: 18,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    shadowColor: colors.ink,
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 2,
  },
  field: { gap: 8 },
  label: { fontSize: 15, fontWeight: "800", color: colors.ink },
  platformField: {
    minHeight: 48,
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 12,
    paddingHorizontal: 14,
    backgroundColor: colors.field,
  },
  platformChip: {
    alignSelf: "flex-start",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: colors.selected,
  },
  platformText: { color: colors.selectedInk, fontSize: 13, fontWeight: "700" },
  choose: {
    minHeight: 150,
    padding: 20,
    borderRadius: 16,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.lineStrong,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.field,
  },
  uploadIcon: { color: colors.primary, fontSize: 28, lineHeight: 32 },
  chooseText: { marginTop: 4, color: colors.selectedInk, fontWeight: "800" },
  chooseHelp: { marginTop: 5, color: colors.muted, fontSize: 11, textAlign: "center" },
  mediaBox: {
    overflow: "hidden",
    borderRadius: 16,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.lineStrong,
    backgroundColor: colors.field,
    padding: 14,
  },
  image: { width: "100%", aspectRatio: 1.35, borderRadius: 12, backgroundColor: colors.lineStrong },
  videoPlaceholder: {
    width: "100%",
    aspectRatio: 1.6,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  playIcon: { color: colors.white, fontSize: 30 },
  videoText: { marginTop: 6, color: colors.white, fontWeight: "800" },
  mediaActions: { flexDirection: "row", alignItems: "center", gap: 12 },
  mediaMeta: { flex: 1, color: colors.muted, fontSize: 12 },
  actionText: { color: colors.primary, fontSize: 12, fontWeight: "800" },
  input: {
    minHeight: 50,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.field,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.ink,
    fontSize: 15,
  },
  textarea: { minHeight: 120 },
  contextRow: {
    minHeight: 52,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: 14,
    paddingHorizontal: 16,
    backgroundColor: colors.subtle,
  },
  checkbox: {
    width: 20,
    height: 20,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: colors.checkboxBorder,
    borderRadius: 4,
    backgroundColor: colors.surface,
  },
  checkboxChecked: { borderColor: colors.primary, backgroundColor: colors.primary },
  check: { color: colors.white, fontSize: 14, fontWeight: "900" },
  contextText: { color: colors.inkSoft, fontWeight: "800" },
  resultCard: {
    gap: 16,
    padding: 18,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    shadowColor: colors.ink,
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 2,
  },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  brandIcon: {
    width: 38,
    height: 38,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 19,
    backgroundColor: colors.primary,
  },
  brandLetters: { color: colors.white, fontSize: 12, fontWeight: "900" },
  brandName: { color: colors.ink, fontSize: 17, fontWeight: "900" },
  brandAccount: { marginTop: 1, color: colors.muted, fontSize: 11 },
  tintedInput: { borderWidth: 0, backgroundColor: colors.field },
  hashtagInput: { color: colors.primary },
  publishNote: { color: "#B45309", fontSize: 13, lineHeight: 19 },
  directNote: { color: colors.muted, fontSize: 12, lineHeight: 18, textAlign: "center" },
});
