# Frontend Architecture Overview

## 📊 Refactoring Results
- **Before**: 754 lines in single App.tsx
- **After**: 343 lines in App.tsx + modular components
- **Improvement**: ~54% reduction in main file size

## 📁 New File Structure

```
frontend/
├── hooks/                          # Custom React Hooks
│   ├── useColorExtraction.ts       # Poster color extraction logic
│   └── useFeaturedContent.ts       # Featured anime loading logic
│
├── components/
│   ├── layout/                     # Layout Components
│   │   ├── Background.tsx          # Dynamic theme-based background
│   │   ├── Header.tsx              # Navigation & theme toggle
│   │   ├── HeroSection.tsx         # Hero text & upload area
│   │   └── FeaturedContent.tsx     # Weekly Top 5 carousel
│   │
│   ├── overlays/                   # Overlay Components
│   │   └── Overlays.tsx            # Notifications & loading overlays
│   │
│   ├── AnimeCard.tsx               # Results display (existing)
│   ├── FileUpload.tsx              # File upload component (existing)
│   ├── VideoPlayer.tsx             # Video player (existing)
│   ├── ThemeList.tsx               # Theme list (existing)
│   └── ConfirmIngestionDialog.tsx  # Ingestion dialog (existing)
│
├── services/
│   └── backendClient.ts            # API client (existing)
│
├── App.tsx                         # Main orchestrator (refactored)
└── types.ts                        # Type definitions (existing)
```

## 🎯 Component Responsibilities

### **App.tsx** (Main Orchestrator)
- State management
- Event handlers
- Component composition
- Business logic coordination

### **Custom Hooks**

#### `useColorExtraction`
- Extracts dominant colors from uploaded images
- Filters out dark/light/transparent pixels
- Returns top 3 colors for theming
- **Exports**: `{ extractedColors, extractColorsFromImage, resetColors }`

#### `useFeaturedContent`
- Fetches trending anime on mount
- Formats data for display
- **Exports**: `{ featuredContent, loadingFeatured }`

### **Layout Components**

#### `Background.tsx`
- Renders theme-specific background
- Dynamic color gradients based on poster
- Animated blobs and stars (dark mode)
- **Props**: `isDarkMode`, `primaryColor`, `secondaryColor`, `tertiaryColor`

#### `Header.tsx`
- Navigation (back button on results)
- Identification mode selector (RAG/Hybrid/Gemini)
- Theme toggle switch
- **Props**: `appState`, `isDarkMode`, `identificationMode`, handlers

#### `HeroSection.tsx`
- Hero text and branding
- File upload component
- Loading and error states
- **Props**: `isDarkMode`, `appState`, `errorMsg`, `onFileSelect`, `onReset`

#### `FeaturedContent.tsx`
- Weekly Top 5 OST carousel
- Hover interactions (play/details)
- Loading skeleton
- **Props**: `featuredContent`, `loadingFeatured`, `onPlayVideo`

### **Overlay Components**

#### `ReidentificationOverlay`
- Loading state during re-identification
- **Props**: `isVisible`

#### `SuccessNotification`
- Success message toast
- Auto-dismissible
- **Props**: `isVisible`, `message`, `onClose`

## 🔄 Data Flow

```
User Action
    ↓
App.tsx (Event Handler)
    ↓
Custom Hook / Component
    ↓
Backend Service
    ↓
Update State
    ↓
Re-render Components
```

## 🎨 Design Patterns Used

1. **Container/Presentational Pattern**
   - App.tsx = Container (logic)
   - Layout components = Presentational (UI)

2. **Custom Hooks Pattern**
   - Encapsulate reusable stateful logic
   - Cleaner component code

3. **Composition Pattern**
   - Small, focused components
   - Compose to build features

4. **Props Drilling Alternative**
   - Callbacks passed down
   - State managed at appropriate levels

## 🚀 Benefits

### Maintainability
- Each component has single responsibility
- Easy to locate and fix bugs
- Clear separation of concerns

### Reusability
- Components can be used elsewhere
- Hooks can be shared across components

### Testability
- Isolated units easy to test
- Mock props/hooks independently

### Scalability
- Add new features without bloating main file
- Team members can work on different components
- Easier code reviews

## 📝 Future Improvements

Consider creating:
- `hooks/useAnimeIdentification.ts` - Encapsulate identification logic
- `hooks/useIngestion.ts` - Manage ingestion flow
- `contexts/ThemeContext.tsx` - Global theme state management
- `utils/colorUtils.ts` - Color manipulation utilities
