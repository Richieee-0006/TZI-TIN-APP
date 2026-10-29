// WebAssembly (AssemblyScript) klientská logika pro TZI Trenér
// Kompilace: npx -p assemblyscript asc wasm/quiz_core.ts -o ui/quiz.wasm --optimize --runtime stub

// Paměťové sloty (offsety v bajtech v lineární paměti WASM):
// 512..1023   : int32 pole pro Fisher-Yates míchání (až 128 prvků)
// 1024..3071  : UTF-16 slot 0 (vstup A / uživatelská odpověď)
// 3072..5119  : UTF-16 slot 1 (vstup B / očekávaná varianta)
// 5120..7167  : UTF-16 slot 2 (normalizovaný výstup A)
// 7168..9215  : UTF-16 slot 3 (normalizovaný výstup B)

export const SHUFFLE_PTR: usize = 512;
export const SLOT0_PTR: usize = 1024;
export const SLOT1_PTR: usize = 3072;
export const SLOT2_PTR: usize = 5120;
export const SLOT3_PTR: usize = 7168;

// Pomocná tabulka pro odstranění české a evropské diakritiky a převod na malá písmena
function foldCharToLowerAscii(c: u16): u16 {
  // Velká ASCII A-Z -> a-z
  if (c >= 65 && c <= 90) return c + 32;
  // Malá ASCII a-z a číslice 0-9
  if ((c >= 97 && c <= 122) || (c >= 48 && c <= 57)) return c;

  switch (c) {
    // á, Á, ä, Ä, à, À, â, Â
    case 0x00E1: case 0x00C1: case 0x00E4: case 0x00C4:
    case 0x00E0: case 0x00C0: case 0x00E2: case 0x00C2:
      return 97; // 'a'
    // č, Č, ç, Ç
    case 0x010D: case 0x010C: case 0x00E7: case 0x00C7:
      return 99; // 'c'
    // ď, Ď
    case 0x010F: case 0x010E:
      return 100; // 'd'
    // é, É, ě, Ě, ë, Ë, è, È, ê, Ê
    case 0x00E9: case 0x00C9: case 0x011B: case 0x011A:
    case 0x00EB: case 0x00CB: case 0x00E8: case 0x00C8:
    case 0x00EA: case 0x00CA:
      return 101; // 'e'
    // í, Í, ï, Ï, ì, Ì, î, Î
    case 0x00ED: case 0x00CD: case 0x00EF: case 0x00CF:
    case 0x00EC: case 0x00CC: case 0x00EE: case 0x00CE:
      return 105; // 'i'
    // ľ, Ľ, ĺ, Ĺ
    case 0x013E: case 0x013D: case 0x013A: case 0x0139:
      return 108; // 'l'
    // ň, Ň, ñ, Ñ
    case 0x0148: case 0x0147: case 0x00F1: case 0x00D1:
      return 110; // 'n'
    // ó, Ó, ö, Ö, ô, Ô, ò, Ò
    case 0x00F3: case 0x00D3: case 0x00F6: case 0x00D6:
    case 0x00F4: case 0x00D4: case 0x00F2: case 0x00D2:
      return 111; // 'o'
    // ř, Ř, ŕ, Ŕ
    case 0x0159: case 0x0158: case 0x0155: case 0x0154:
      return 114; // 'r'
    // š, Š
    case 0x0161: case 0x0160:
      return 115; // 's'
    // ť, Ť
    case 0x0165: case 0x0164:
      return 116; // 't'
    // ú, Ú, ů, Ů, ü, Ü, ù, Ù, û, Û
    case 0x00FA: case 0x00DA: case 0x016F: case 0x016E:
    case 0x00FC: case 0x00DC: case 0x00F9: case 0x00D9:
    case 0x00FB: case 0x00DB:
      return 117; // 'u'
    // ý, Ý, ÿ, Ÿ
    case 0x00FD: case 0x00DD: case 0x00FF: case 0x0178:
      return 121; // 'y'
    // ž, Ž
    case 0x017E: case 0x017D:
      return 122; // 'z'
    default:
      return c;
  }
}

function isRecallPunctOrSpace(c: u16): bool {
  if (c <= 32 || c == 0x00A0) return true;
  // .[46] ,[44] ;[59] :[58] ![33] ?[63] '[39] "[34] ([40] )[41] [[91] ][93] {[123] }[125] _[95] /[47] -[45]
  switch (c) {
    case 46: case 44: case 59: case 58: case 33: case 63:
    case 39: case 34: case 40: case 41: case 91: case 93:
    case 123: case 125: case 95: case 47: case 45:
    case 0x201E: case 0x201C: case 0x201D: case 0x201A: case 0x2018: case 0x2019:
    case 0x2026: case 0x2013: case 0x2014: case 0x2212:
      return true;
    default:
      return false;
  }
}

function toUpperCode(c: u16): u16 {
  if (c >= 97 && c <= 122) return c - 32;
  // České malé znaky na velké
  switch (c) {
    case 0x00E1: return 0x00C1;
    case 0x010D: return 0x010C;
    case 0x010F: return 0x010E;
    case 0x00E9: return 0x00C9;
    case 0x011B: return 0x011A;
    case 0x00ED: return 0x00CD;
    case 0x0148: return 0x0147;
    case 0x00F3: return 0x00D3;
    case 0x0159: return 0x0158;
    case 0x0161: return 0x0160;
    case 0x0165: return 0x0164;
    case 0x00FA: return 0x00DA;
    case 0x016F: return 0x016E;
    case 0x00FD: return 0x00DD;
    case 0x017E: return 0x017D;
    default: return c;
  }
}

// Fisher-Yates zamíchání pole int32 na adrese SHUFFLE_PTR
export function shuffleIndices(len: i32, seed: u32): void {
  for (let i: i32 = 0; i < len; i++) {
    store<i32>(SHUFFLE_PTR + (<usize>i << 2), i);
  }
  let state: u32 = seed ? seed : 0x9E3779B9;
  for (let i: i32 = len - 1; i > 0; i--) {
    state += 0x6D2B79F5;
    let t: u32 = state;
    t = (t ^ (t >>> 15)) * (t | 1);
    t ^= t + (t ^ (t >>> 7)) * (t | 61);
    const rnd: u32 = (t ^ (t >>> 14)) >>> 0;
    const j: i32 = <i32>((<u64>rnd * <u64>(i + 1)) >> 32);

    const addrI: usize = SHUFFLE_PTR + (<usize>i << 2);
    const addrJ: usize = SHUFFLE_PTR + (<usize>j << 2);
    const tmp: i32 = load<i32>(addrI);
    store<i32>(addrI, load<i32>(addrJ));
    store<i32>(addrJ, tmp);
  }
}

// Normalizace pro číselné a přesné odpovědi (norm):
// velká písmena, bez mezer a '_', oříznuté úvodní nuly (kromě samotné '0')
export function normInput(srcPtr: usize, len: i32, dstPtr: usize): i32 {
  let outLen: i32 = 0;
  for (let i: i32 = 0; i < len; i++) {
    const c: u16 = load<u16>(srcPtr + (<usize>i << 1));
    if (c <= 32 || c == 0x00A0 || c == 95) continue;
    store<u16>(dstPtr + (<usize>outLen << 1), toUpperCode(c));
    outLen++;
  }
  // Odstranit úvodní nuly, pokud za nimi následuje aspoň jeden znak
  let zeroCount: i32 = 0;
  while (zeroCount < outLen - 1 && load<u16>(dstPtr + (<usize>zeroCount << 1)) == 48) {
    zeroCount++;
  }
  if (zeroCount > 0) {
    const newLen: i32 = outLen - zeroCount;
    for (let i: i32 = 0; i < newLen; i++) {
      store<u16>(dstPtr + (<usize>i << 1), load<u16>(dstPtr + (<usize>(i + zeroCount) << 1)));
    }
    return newLen;
  }
  return outLen;
}

// Normalizace pro doplňovačku (recallNorm):
// malá písmena, bez diakritiky, interpunkce -> mezera, vícenásobné mezery -> 1 mezera, trim
export function recallNormBuf(srcPtr: usize, len: i32, dstPtr: usize): i32 {
  let outLen: i32 = 0;
  let lastWasSpace: bool = true; // pro oříznutí úvodních mezer

  for (let i: i32 = 0; i < len; i++) {
    const raw: u16 = load<u16>(srcPtr + (<usize>i << 1));
    // Ignorovat Unicode combining diacritical marks (U+0300..U+036F)
    if (raw >= 0x0300 && raw <= 0x036F) continue;

    if (isRecallPunctOrSpace(raw)) {
      if (!lastWasSpace) {
        store<u16>(dstPtr + (<usize>outLen << 1), 32);
        outLen++;
        lastWasSpace = true;
      }
    } else {
      const folded: u16 = foldCharToLowerAscii(raw);
      store<u16>(dstPtr + (<usize>outLen << 1), folded);
      outLen++;
      lastWasSpace = false;
    }
  }

  if (outLen > 0 && load<u16>(dstPtr + (<usize>(outLen - 1) << 1)) == 32) {
    outLen--;
  }
  return outLen;
}

// Levenshteinova vzdálenost <= 1 mezi dvěma UTF-16 řetězci v paměti
export function lev1Buf(ptrA: usize, lenA: i32, ptrB: usize, lenB: i32): i32 {
  const diff: i32 = lenA > lenB ? lenA - lenB : lenB - lenA;
  if (diff > 1) return 0;

  let i: i32 = 0;
  const minLen: i32 = lenA < lenB ? lenA : lenB;
  while (i < minLen && load<u16>(ptrA + (<usize>i << 1)) == load<u16>(ptrB + (<usize>i << 1))) {
    i++;
  }
  if (i == lenA && i == lenB) return 1;

  if (lenA == lenB) {
    // Záměna jednoho znaku: zbytek od i+1 se musí shodovat
    for (let k: i32 = i + 1; k < lenA; k++) {
      if (load<u16>(ptrA + (<usize>k << 1)) != load<u16>(ptrB + (<usize>k << 1))) return 0;
    }
    return 1;
  } else if (lenA > lenB) {
    // Vypuštění znaku z A: A[i+1..] == B[i..]
    for (let k: i32 = i; k < lenB; k++) {
      if (load<u16>(ptrA + (<usize>(k + 1) << 1)) != load<u16>(ptrB + (<usize>k << 1))) return 0;
    }
    return 1;
  } else {
    // Vypuštění znaku z B: A[i..] == B[i+1..]
    for (let k: i32 = i; k < lenA; k++) {
      if (load<u16>(ptrA + (<usize>k << 1)) != load<u16>(ptrB + (<usize>(k + 1) << 1))) return 0;
    }
    return 1;
  }
}

function areBuffersEqual(ptrA: usize, lenA: i32, ptrB: usize, lenB: i32): bool {
  if (lenA != lenB) return false;
  for (let i: i32 = 0; i < lenA; i++) {
    if (load<u16>(ptrA + (<usize>i << 1)) != load<u16>(ptrB + (<usize>i << 1))) return false;
  }
  return true;
}

function isPureLowerAsciiWord(ptr: usize, len: i32): bool {
  for (let i: i32 = 0; i < len; i++) {
    const c: u16 = load<u16>(ptr + (<usize>i << 1));
    if (c < 97 || c > 122) return false;
  }
  return true;
}

// Porovnání normalizované odpovědi (v SLOT2_PTR, délka lenA) s normalizovanou variantou (v SLOT3_PTR, délka lenV)
// Vrací: 0 = neshoda, 1 = přesná shoda, 2 = shoda s tolerancí 1 překlepu
export function matchNormalizedRecall(lenA: i32, lenV: i32): i32 {
  if (lenA <= 0 || lenV <= 0) return 0;
  if (areBuffersEqual(SLOT2_PTR, lenA, SLOT3_PTR, lenV)) return 1;

  // Rozdělení na slova po mezerách (32) a porovnání po slovech
  let idxA: i32 = 0;
  let idxV: i32 = 0;

  while (idxA < lenA && idxV < lenV) {
    let endA: i32 = idxA;
    while (endA < lenA && load<u16>(SLOT2_PTR + (<usize>endA << 1)) != 32) endA++;

    let endV: i32 = idxV;
    while (endV < lenV && load<u16>(SLOT3_PTR + (<usize>endV << 1)) != 32) endV++;

    const wLenA: i32 = endA - idxA;
    const wLenV: i32 = endV - idxV;
    const wPtrA: usize = SLOT2_PTR + (<usize>idxA << 1);
    const wPtrV: usize = SLOT3_PTR + (<usize>idxV << 1);

    if (!areBuffersEqual(wPtrA, wLenA, wPtrV, wLenV)) {
      // Překlep povolen jen u slov delších než 5 písmen (pouze a-z) se stejným 1. písmenem
      if (wLenV <= 5 || wLenA <= 0) return 0;
      if (!isPureLowerAsciiWord(wPtrV, wLenV)) return 0;
      if (load<u16>(wPtrV) != load<u16>(wPtrA)) return 0;
      if (lev1Buf(wPtrV, wLenV, wPtrA, wLenA) == 0) return 0;
    }

    idxA = endA + 1;
    idxV = endV + 1;
  }

  // Obě věty musí skončit současně (stejný počet slov)
  if (idxA < lenA || idxV < lenV) return 0;
  return 2;
}

// Vyhodnocení otázky typu choice pomocí bitové masky
export function evaluateChoiceMask(selectedMask: i32, correctMask: i32): i32 {
  return (correctMask != 0 && selectedMask == correctMask) ? 1 : 0;
}

// Vyhodnocení otázky typu input (vstup v SLOT0_PTR, správná odpověď v SLOT1_PTR)
export function evaluateInputBuffers(userLen: i32, expLen: i32): i32 {
  const nU: i32 = normInput(SLOT0_PTR, userLen, SLOT2_PTR);
  const nE: i32 = normInput(SLOT1_PTR, expLen, SLOT3_PTR);
  return areBuffersEqual(SLOT2_PTR, nU, SLOT3_PTR, nE) ? 1 : 0;
}

// Ceská pluralizace: 0 = jednotné (1), 1 = 2..4, 2 = 0 nebo >=5
export function pluralCategory(n: i32): i32 {
  const absN: i32 = n < 0 ? -n : n;
  if (absN == 1) return 0;
  if (absN >= 2 && absN <= 4) return 1;
  return 2;
}

// Výpocet procent (0..100) se zaokrouhlením
export function calcPercentage(part: i32, total: i32): i32 {
  if (part <= 0) return 0;
  const denom: i32 = total > 1 ? total : 1;
  const pct: i32 = (part * 100 + (denom >> 1)) / denom;
  return pct > 100 ? 100 : pct;
}

// Hranice 60 % pro ostrý test: ceil(total * 0.6)
export function calcExamNeeded(total: i32): i32 {
  if (total <= 0) return 0;
  return (total * 3 + 4) / 5;
}

// Výpocet úrovne hrace (1..7) podle XP
export function calcRankLevel(xp: i32): i32 {
  if (xp >= 1200) return 7;
  if (xp >= 800) return 6;
  if (xp >= 500) return 5;
  if (xp >= 300) return 4;
  if (xp >= 150) return 3;
  if (xp >= 50) return 2;
  return 1;
}

// Výpocet procent postupu v aktuální úrovni (0..100)
export function calcRankPct(xp: i32): i32 {
  let minXp: i32 = 0;
  let maxXp: i32 = 50;
  if (xp >= 1200) { minXp = 1200; maxXp = 2000; }
  else if (xp >= 800) { minXp = 800; maxXp = 1200; }
  else if (xp >= 500) { minXp = 500; maxXp = 800; }
  else if (xp >= 300) { minXp = 300; maxXp = 500; }
  else if (xp >= 150) { minXp = 150; maxXp = 300; }
  else if (xp >= 50) { minXp = 50; maxXp = 150; }
  return calcPercentage(xp - minXp, maxXp - minXp);
}

// Výpocet bitové masky odemcených odznaku (achievements)
export function calcAchievementMask(xp: i32, bestStreak: i32, dStreak: i32, goalMet: i32, doneCount: i32, hasWrong: i32): i32 {
  let mask: i32 = 0;
  if (xp > 0 || doneCount >= 1) mask |= (1 << 0);       // first
  if (doneCount >= 5 || xp >= 15) mask |= (1 << 1);     // start
  if (bestStreak >= 5) mask |= (1 << 2);                // wave
  if (bestStreak >= 15) mask |= (1 << 3);               // invincible
  if (doneCount >= 50 || xp >= 150) mask |= (1 << 4);   // fifty
  if (doneCount >= 200 || xp >= 600) mask |= (1 << 5);  // twohundred
  if (doneCount >= 100) mask |= (1 << 6);               // marathon
  if (hasWrong != 0 && doneCount >= 3) mask |= (1 << 7);// learn
  if (xp >= 100) mask |= (1 << 8);                      // memory
  if (dStreak >= 3) mask |= (1 << 9);                   // regular
  if (dStreak >= 7) mask |= (1 << 10);                  // week
  if (bestStreak >= 3) mask |= (1 << 11);               // lucky
  if (xp >= 30) mask |= (1 << 12);                      // fast
  if (goalMet != 0) mask |= (1 << 13);                  // done
  if (dStreak >= 2) mask |= (1 << 14);                  // routine
  if (xp >= 500) mask |= (1 << 15);                     // advanced
  if (xp >= 1200) mask |= (1 << 16);                    // master
  return mask;
}

// Výpocet úspesnosti (accuracy 0..100) ze správných a chybných odpovedí
export function calcRecapAccuracy(correct: i32, wrong: i32): i32 {
  const answered: i32 = correct + wrong;
  if (answered <= 0 || correct <= 0) return 0;
  return calcPercentage(correct, answered);
}
