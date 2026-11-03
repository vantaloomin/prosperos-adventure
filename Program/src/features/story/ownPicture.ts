// The player's own picture for a portrait (adventure/art.py own_portrait), from Prospero's Companion #454.

/** The file types a picture may come in. */
export const PICTURE_TYPES = 'image/png,image/jpeg,image/webp'

/** The size it is shrunk to on its longer side before it is sent. */
export const LONGEST = 2048

/** The width and height a picture is sent at: its own when it fits, else shrunk to LONGEST on its longer side. */
export function shrunk(width: number, height: number): { width: number; height: number } {
  const scale = Math.min(1, LONGEST / Math.max(width, height))
  return { width: Math.round(width * scale), height: Math.round(height * scale) }
}

/** The user's own picture as PNG or JPEG, at most LONGEST px on its longer side. Runs only in the browser. */
export async function pictureCopy(file: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(file)
  const size = shrunk(bitmap.width, bitmap.height)
  const type = file.type === 'image/png' ? 'image/png' : 'image/jpeg'
  if (size.width === bitmap.width && type === file.type) {
    bitmap.close()
    return file
  }
  const canvas = document.createElement('canvas')
  canvas.width = size.width
  canvas.height = size.height
  canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return new Promise((resolve, reject) => canvas.toBlob((copy) => copy ? resolve(copy) : reject(new Error('This picture could not be read.')), type, 0.92))
}
