// The photo you are working on, shared by Analyze and Compare so moving
// between them keeps it. It lives in memory only: reloading the page forgets
// it, and nothing is uploaded until a page actually runs an analysis.

let photo = null;   // File
let scan = null;    // the latest scan made from that photo
let scanOf = null;  // key of the photo that scan belongs to

const keyOf = (file) => (file ? [file.name, file.size, file.lastModified].join('|') : null);

export const currentPhoto = {
  get: () => photo,

  set(file) {
    if (keyOf(file) !== keyOf(photo)) { scan = null; scanOf = null; }
    photo = file || null;
  },

  /** Remember the result of an analysis of `file`. */
  rememberScan(file, result) {
    photo = file;
    scan = result;
    scanOf = keyOf(file);
  },

  /** The latest scan of the current photo, if there is one. */
  scan: () => (photo && scanOf === keyOf(photo) ? scan : null),
};
