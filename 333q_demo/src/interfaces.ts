// D7 fix: type-only interface lock pre-W1 (Naesengmoon SP gate requirement)
// KG: span-333q-state-vector-2026-05-20 ↔ span-333q-mermin-ghz-2026-05-20 ↔ span-333q-yjs-state-2026-05-20

/** Wire format for a 6-qubit state vector. */
export interface StateVectorWire {
  readonly qubits: 6;
  readonly amplitudesRe: Float32Array;
  readonly amplitudesIm: Float32Array;
  readonly normValid: boolean;
}

/** Measurement basis selector. */
export type MeasurementBasis = 'Z' | 'X' | 'Y' | 'GHZ_X' | 'GHZ_Y';

/** Born rule sampling output. */
export interface MeasurementOutcome {
  readonly outcomeBits: ReadonlyArray<0 | 1>;
  readonly probability: number;
  readonly postStateRef: string;
  readonly basis: MeasurementBasis;
  readonly timestampLamport: number;
}

/** Mermin GHZ game input/output per player. */
export interface GHZRound {
  readonly playerId: string;
  readonly inputBit: 0 | 1;
  readonly outputBit: 0 | 1;
  readonly strategyKind: 'classical_random' | 'classical_best_table' | 'quantum_encoded';
}

/** 3-player joint round result. */
export interface GHZJointResult {
  readonly rounds: readonly [GHZRound, GHZRound, GHZRound];
  readonly inputsSumEven: boolean;
  readonly outputParity: 0 | 1;
  readonly expectedParity: 0 | 1;
  readonly won: boolean;
  readonly seedHashSha256: string;
}

/** Trystero room handshake state. */
export interface TrysteroRoomState {
  readonly roomId: string;
  readonly peerIds: ReadonlyArray<string>;
  readonly readyPeers: ReadonlyArray<string>;
  readonly allReady: boolean;
  readonly handshakeStartMs: number;
  readonly handshakeReadyMs: number | null;
}

/** Pre-shared seed entropy distribution channel payload. */
export interface EntropySeedPacket {
  readonly seedHexSha256: string;
  readonly senderPeerId: string;
  readonly ed25519Signature: string;
  readonly publishedAtLamport: number;
}

/** Yjs OR-Set entanglement edge. */
export interface EntanglementEdge {
  readonly peerA: string;
  readonly peerB: string;
  readonly qubitIdx: number;
  readonly addedAtLamport: number;
  readonly addTag: string;
}

/** LWW Register per qubit state. */
export interface QubitStateRegister {
  readonly qubitIdx: number;
  readonly eigenstateValue: 0 | 1 | null;
  readonly lastWriteLamport: number;
  readonly writerPeerId: string;
}

/** Quorum-witnessed collapse event (D5 fix: renamed from atomic-broadcast). */
export interface CollapseEvent {
  readonly eventId: string;
  readonly qubitIdx: number;
  readonly outcomeBit: 0 | 1;
  readonly witnessSignatures: ReadonlyArray<{
    readonly peerId: string;
    readonly ed25519Signature: string;
  }>;
  readonly quorumReached: boolean;
  readonly emittedAtLamport: number;
}

/** Koan sign harvest record. */
export interface KoanSign {
  readonly id: string;
  readonly imageRefSvgPath: string;
  readonly textShortKr: string;
  readonly sourceCanon: 'mumonkan_inspired' | 'bruce_original_mock';
  readonly triggerPredicate: 'early_observe' | 'late_defer' | 'mismatch' | 'agreement';
}
