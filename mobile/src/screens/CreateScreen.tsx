import { useRef, useState } from 'react';
import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { GoalDropdown } from '../components/GoalDropdown';
import { Button } from '../components/ui';
import { generateCaption } from '../services/caption';
import { Draft, ImageMimeType, InstagramConnection, SocialPlatform } from '../types';

const PLATFORMS: SocialPlatform[] = ['Instagram', 'Twitter', 'Facebook', 'Threads', 'YouTube'];
const SUPPORTED_IMAGE_TYPES: ImageMimeType[] = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

export function CreateScreen({ draft, setDraft, connection: _connection, accessToken, onPreview }: { draft: Draft; setDraft: (value: Draft) => void; connection: InstagramConnection | null; accessToken: string; onPreview: () => void }) {
  const scroll = useRef<ScrollView>(null);
  const [open, setOpen] = useState(false);
  const [generating, setGenerating] = useState(false);

  const pick = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      quality: 0.85,
      base64: true,
    });
    if (result.canceled) return;

    const asset = result.assets[0];
    const mimeType = asset.mimeType as ImageMimeType | undefined;
    if (!mimeType || !SUPPORTED_IMAGE_TYPES.includes(mimeType)) {
      Alert.alert('Unsupported image', 'Choose a JPG, PNG or WebP image. Video is not supported yet.');
      return;
    }
    if (asset.fileSize && asset.fileSize > MAX_IMAGE_BYTES) {
      Alert.alert('Image too large', 'Choose an image smaller than 5 MB.');
      return;
    }
    if (!asset.base64) {
      Alert.alert('Could not read image', 'Please choose the image again.');
      return;
    }

    setDraft({
      ...draft,
      imageUri: asset.uri,
      imageData: asset.base64,
      imageMimeType: mimeType,
      hasResults: false,
    });
  };

  const create = async () => {
    if (!draft.imageUri || !draft.imageData || !draft.imageMimeType) return Alert.alert('Choose an image');
    if (!draft.information.trim()) return Alert.alert('Add information');
    if (!draft.goal || (draft.goal === 'Other' && !draft.otherGoal.trim())) return Alert.alert('Choose a goal');

    setGenerating(true);
    try {
      const result = await generateCaption({
        information: draft.information,
        goal: draft.goal === 'Other' ? draft.otherGoal.trim() : draft.goal,
        platform: draft.platform,
        image: { mime_type: draft.imageMimeType, data: draft.imageData },
      }, accessToken);
      setDraft({ ...draft, ...result, hasResults: true });
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
    } catch (error) {
      Alert.alert('Generation failed', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <ScrollView ref={scroll} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag">
      <Text style={styles.title}>Create post</Text>

      {draft.imageUri ? (
        <View style={styles.imageWrap}>
          <Image source={{ uri: draft.imageUri }} style={styles.image} />
          <View style={styles.imageActions}>
            <Button label="Change image" onPress={pick} secondary />
            <Button label="Remove image" onPress={() => setDraft({ ...draft, imageUri: undefined, imageData: undefined, imageMimeType: undefined, hasResults: false })} secondary />
          </View>
        </View>
      ) : (
        <Pressable accessibilityRole="button" onPress={pick} style={styles.choose}>
          <Text style={styles.chooseText}>Choose image</Text>
        </Pressable>
      )}

      <View style={styles.field}>
        <Text style={styles.label}>Social platform</Text>
        <View style={styles.platforms}>
          {PLATFORMS.map((platform) => {
            const selected = platform === draft.platform;
            return (
              <Pressable
                key={platform}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                onPress={() => setDraft({ ...draft, platform, hasResults: false })}
                style={[styles.platform, selected && styles.platformSelected]}
              >
                <Text style={[styles.platformText, selected && styles.platformTextSelected]}>{platform}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      <Field label="Information" value={draft.information} onChangeText={(information) => setDraft({ ...draft, information, hasResults: false })} placeholder="Describe your content, audience and key message" multiline />
      <GoalDropdown value={draft.goal} open={open} onToggle={() => setOpen(!open)} onSelect={(goal) => { setDraft({ ...draft, goal, otherGoal: goal === 'Other' ? draft.otherGoal : '', hasResults: false }); setOpen(false); }} />
      {draft.goal === 'Other' && <Field label="Other goal" value={draft.otherGoal} onChangeText={(otherGoal) => setDraft({ ...draft, otherGoal: otherGoal.slice(0, 200), hasResults: false })} placeholder="Describe your goal" maxLength={200} />}
      <Button label={generating ? 'Creating…' : 'Create caption'} onPress={create} disabled={generating} />

      {draft.hasResults && draft.imageUri && (
        <View style={styles.results}>
          <Text style={styles.resultsTitle}>Generated copy</Text>
          <Field label="Caption" value={draft.caption} onChangeText={(caption) => setDraft({ ...draft, caption })} placeholder="Caption" multiline />
          <Field label="Hashtags" value={draft.hashtags} onChangeText={(hashtags) => setDraft({ ...draft, hashtags })} placeholder="#postbridge" multiline />
          {draft.platform === 'Instagram' ? (
            <Button label="Open publish preview" onPress={onPreview} secondary />
          ) : (
            <Text style={styles.publishNote}>{draft.platform} publishing will be added after its platform connection is available.</Text>
          )}
        </View>
      )}
    </ScrollView>
  );
}

function Field(props: { label: string; value: string; onChangeText: (value: string) => void; placeholder: string; multiline?: boolean; maxLength?: number }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{props.label}</Text>
      <TextInput {...props} style={[styles.input, props.multiline && styles.textarea]} textAlignVertical="top" />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 32, gap: 14 },
  title: { fontSize: 30, lineHeight: 36, fontWeight: '800', color: '#201633' },
  choose: { height: 150, borderRadius: 18, borderWidth: 1, borderStyle: 'dashed', borderColor: '#b9aec8', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f1edf7' },
  chooseText: { color: '#5b21b6', fontWeight: '800' },
  imageWrap: { gap: 10 },
  image: { width: '100%', aspectRatio: 1.35, borderRadius: 18, backgroundColor: '#ddd' },
  imageActions: { flexDirection: 'row', gap: 10 },
  field: { gap: 7 },
  label: { fontWeight: '700', color: '#342846' },
  input: { minHeight: 50, borderWidth: 1, borderColor: '#ddd5e8', backgroundColor: 'white', borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12, color: '#201633' },
  textarea: { minHeight: 105 },
  platforms: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  platform: { borderWidth: 1, borderColor: '#ddd5e8', borderRadius: 999, backgroundColor: 'white', paddingHorizontal: 14, paddingVertical: 10 },
  platformSelected: { borderColor: '#7c3aed', backgroundColor: '#eee8ff' },
  platformText: { color: '#5f566c', fontWeight: '700' },
  platformTextSelected: { color: '#6d28d9' },
  results: { gap: 14 },
  resultsTitle: { fontSize: 22, fontWeight: '800', color: '#201633' },
  publishNote: { color: '#746b82', fontSize: 13, lineHeight: 19 },
});
