# Problem 129: Design Figma (Real-Time Collaborative Design Tool)

## Problem Statement

Design a real-time collaborative design tool like Figma where multiple users can simultaneously edit vector graphics on a shared canvas with instant synchronization.

## Key Challenges

### Real-Time Multiplayer Editing
- Multiple cursors visible simultaneously
- Instant propagation of edits (< 100ms perceived latency)
- Conflict resolution for concurrent property modifications
- Presence awareness (who is viewing/editing what)

### CRDT for Vector Graphics
- Hierarchical document model (pages, frames, layers, shapes)
- Concurrent tree operations (move, reparent, reorder)
- Property-level conflict resolution (last-writer-wins for individual properties)
- Tombstones and garbage collection for deleted elements

### Cursor and Selection Sharing
- Real-time cursor position broadcasting
- Selection highlighting with user color coding
- Viewport awareness (what area each user is viewing)
- Follow-mode (observe another user's view)

### Component System
- Master components with overridable properties
- Instance inheritance and override tracking
- Variant definitions and switching
- Cross-file component libraries

### Version History with Branching
- Auto-save with meaningful version points
- Named versions (like git tags)
- Branching for design exploration
- Merge/diff between branches

### Offline Support
- Local editing without connectivity
- Sync and merge when reconnecting
- Conflict visualization and resolution UI

### Plugin Architecture
- Sandboxed plugin execution environment
- API access to document model
- UI extension points
- Plugin marketplace and distribution

### Rendering Engine
- WebGL/Canvas-based vector rendering
- GPU-accelerated operations (blur, shadows, masks)
- Efficient rendering of millions of objects
- Zoom levels from 0.01% to 25600%

## Scale Requirements

- 100+ simultaneous editors per file
- Millions of objects per canvas
- Sub-frame (< 16ms) render times
- Documents up to 1GB in size
- Global user base with low latency worldwide

## Expected Output

Provide a complete system design covering the collaborative editing protocol, document model, rendering architecture, and component system.
