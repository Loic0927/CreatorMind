# Selection control inventory

Updated: 2026-11-01

## Primitive decision

The web app previously had no accessible UI primitive installed: its only UI dependencies were React, Next.js, and Tailwind. `react-aria-components` (Apache-2.0) is now the accessibility foundation for the shared `UnifiedSelect`. It supplies the listbox option model, keyboard navigation, type-ahead, focus handling, disabled options, overlay dismissal, portal rendering, and adaptive positioning. PostBridge owns only the wrapper API and visual theme.

Expo had no picker or bottom-sheet dependency. The shared `UnifiedPicker` uses React Native's native `Modal`, `Pressable`, `FlatList`, `TextInput`, and accessibility roles/states. This avoids adding a native module and keeps the picker keyboard-free, screen-reader-labelled, and compatible with the existing managed Expo app.

## Active web controls

| Screen / control | File | Mode | Options | Other field | Result |
| --- | --- | --- | ---: | --- | --- |
| Create / Social platforms | `frontend/src/components/dashboard/LegacyCreate.tsx` | Multi | 5 | No | Replaced custom `<details>` checkbox list with `UnifiedSelect` |
| Create / Hashtag count | `frontend/src/components/dashboard/LegacyCreate.tsx` | Single, searchable | 11 | No | Replaced native `<select>`; string UI key is converted back to the original number |
| Create / Goal | `frontend/src/components/dashboard/LegacyCreate.tsx` | Single | 6 | Yes, `Other` | Replaced native `<select>` and moved the existing custom goal input into the shared pattern |
| Create / Use account context | `frontend/src/components/dashboard/LegacyCreate.tsx` | Boolean checkbox | 2 states | No | Kept as a checkbox; it is a standalone Boolean preference, not a dropdown, picker, or checkbox list |
| Settings / Tone | `frontend/src/components/dashboard/LegacySettings.tsx` | Multi, max 3 | 8 | No | Replaced custom `<details>` checkbox list with `UnifiedSelect` |
| Settings / Content format | `frontend/src/components/dashboard/LegacySettings.tsx` | Multi | 5 | No | Replaced custom `<details>` checkbox list with `UnifiedSelect` |
| Settings / Caption language | `frontend/src/components/dashboard/LegacySettings.tsx` | Single | 8 | The option `other` exists, but there is no corresponding stored text field | Replaced native `<select>`; no unpersisted text field was invented |
| Settings / Primary category | `frontend/src/components/dashboard/LegacySettings.tsx` | Single | 9 | Yes, `other`, stored in existing `primary_category_other` | Replaced native `<select>` with `UnifiedSelect` |
| Settings / Audience age range | `frontend/src/components/dashboard/LegacySettings.tsx` | Multi | 7 | No | Replaced custom `<details>` checkbox list with `UnifiedSelect` |
| Insights / Sort | `frontend/src/components/dashboard/WireframeInsights.tsx` | Single, compact | 7 | No | Replaced native `<select>` and text chevron with compact `UnifiedSelect` |

The web source now contains no native `<select>`, `<option>`, or one-off `<details>` dropdown.

## Active Expo controls

| Screen / control | File | Mode | Options | Other field | Result |
| --- | --- | --- | ---: | --- | --- |
| Create / Social platform | `mobile/src/screens/CreateScreen.tsx` | Multi | 5 | No | Replaced the pill checkbox list with `UnifiedPicker` |
| Create / Goal | `mobile/src/screens/CreateScreen.tsx` | Single, searchable | 10 | Yes, `Other` | Replaced `GoalDropdown`; the old component and test were removed |
| Insights / Sort | `mobile/src/screens/InsightsScreen.tsx` | Single, compact | 7 | No | Replaced the cycle-on-press control with `UnifiedPicker` |

Expo Settings currently has Account and Connected accounts actions only; it contains no dropdown, select, checkbox list, or picker.

## Content pickers and justified exceptions

These controls select content objects using image/card grids. Converting them to a text listbox would change the surrounding page layout and the task itself, which the selection-control brief explicitly forbids.

| Screen / control | File | Mode | Option count | Why it remains a content grid |
| --- | --- | --- | ---: | --- |
| Web Home / Choose an Instagram post | `frontend/src/app/dashboard/page.tsx` | Single, immediate action | Dynamic | Thumbnail identity is essential; choosing immediately starts the existing tracking flow |
| Web Analyze / Choose a tracked post | `frontend/src/components/dashboard/WireframeAnalyze.tsx` | Single navigation | Dynamic | Cards show thumbnail and three metrics, not a form value |
| Expo Home / Add a post | `mobile/src/screens/HomeScreen.tsx` | Single, immediate action | Dynamic | Native full-screen media grid; choosing starts tracking |
| Expo Analyze / Choose a tracked post | `mobile/src/screens/TrackingReportScreen.tsx` | Single navigation | Dynamic | Post cards are navigation content rather than a stored picker value |

The OS image library opened by `expo-image-picker` and the web file input are also excluded: they are native media/file pickers and must retain platform-native permissions and file-selection behavior.

## Shared behavior

- Web variants: single, multi with optional maximum, and compact.
- Desktop web: portalled popover, trigger-width sizing, automatic vertical flip, outside/Escape dismissal, one open control at a time, search above eight options, and React Aria keyboard/type-ahead behavior.
- Web below 640px: scrim and bottom sheet with handle, 48px rows, title, and multi-select Done action.
- Expo: native bottom sheet for every variant, 48px rows, search above eight options, chips, disabled-at-max options, accessible radio/checkbox state, and Done for multi-select.
- Shared values remain controlled by each page. No API payload name, Account Context key, value, label, option order, or storage behavior was changed.
