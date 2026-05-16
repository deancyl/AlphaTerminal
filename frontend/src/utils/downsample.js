/**
 * LTTB (Largest-Triangle-Three-Buckets) Downsampling Algorithm
 *
 * Reduces large datasets while preserving visual characteristics.
 * Optimal for chart rendering with thousands of data points.
 *
 * Usage:
 *   const downsampled = downsampleLTTB(klineData, 500)
 */

export function downsampleLTTB(data, threshold) {
  if (!data || data.length <= threshold) {
    return data
  }

  const result = []
  const bucketSize = (data.length - 2) / (threshold - 2)

  result.push(data[0])

  let a = 0

  for (let i = 0; i < threshold - 2; i++) {
    let avgRangeStart = Math.floor((i + 0) * bucketSize) + 1
    let avgRangeEnd = Math.floor((i + 1) * bucketSize) + 1
    const avgRangeLength = avgRangeEnd - avgRangeStart

    let maxArea = -1
    let maxAreaIndex = -1

    const rangeStart = Math.floor(i * bucketSize) + 1
    const rangeEnd = Math.floor((i + 1) * bucketSize) + 1

    const pointAX = a
    const pointAY = data[a].close || data[a].value || data[a]

    for (let j = rangeStart; j < rangeEnd && j < data.length; j++) {
      const pointBX = j
      const pointBY = data[j].close || data[j].value || data[j]

      let avgX = 0
      let avgY = 0

      for (let k = avgRangeStart; k < avgRangeEnd && k < data.length; k++) {
        avgX += k
        avgY += data[k].close || data[k].value || data[k]
      }

      avgX /= avgRangeLength
      avgY /= avgRangeLength

      const area = Math.abs(
        (pointAX - avgX) * (pointBY - pointAY) -
        (pointBX - avgX) * (pointAY - avgY)
      )

      if (area > maxArea) {
        maxArea = area
        maxAreaIndex = j
      }
    }

    if (maxAreaIndex >= 0) {
      result.push(data[maxAreaIndex])
      a = maxAreaIndex
    }
  }

  result.push(data[data.length - 1])

  return result
}

export function downsampleOHLCV(data, threshold) {
  if (!data || data.length <= threshold) {
    return data
  }

  const result = []
  const bucketSize = Math.ceil(data.length / threshold)

  for (let i = 0; i < data.length; i += bucketSize) {
    const bucket = data.slice(i, i + bucketSize)

    if (bucket.length === 0) continue

    const aggregated = {
      date: bucket[0].date,
      time: bucket[0].time,
      open: bucket[0].open,
      high: Math.max(...bucket.map(d => d.high)),
      low: Math.min(...bucket.map(d => d.low)),
      close: bucket[bucket.length - 1].close,
      volume: bucket.reduce((sum, d) => sum + (d.volume || 0), 0),
      change_pct: bucket[bucket.length - 1].change_pct
    }

    result.push(aggregated)
  }

  return result
}

export function smartDownsample(data, threshold, preservePeaks = true) {
  if (!data || data.length <= threshold) {
    return data
  }

  if (!preservePeaks) {
    return downsampleLTTB(data, threshold)
  }

  const peaks = findPeaks(data)
  const peakIndices = new Set(peaks.map(p => p.index))

  const result = []
  const bucketSize = (data.length - 2) / (threshold - 2 - peaks.length)

  result.push(data[0])

  let lastAddedIndex = 0

  for (let i = 0; i < threshold - 2 - peaks.length; i++) {
    const rangeStart = Math.floor(i * bucketSize) + 1
    const rangeEnd = Math.floor((i + 1) * bucketSize) + 1

    let maxArea = -1
    let maxAreaIndex = -1

    for (let j = rangeStart; j < rangeEnd && j < data.length - 1; j++) {
      if (peakIndices.has(j)) continue

      const area = calculateTriangleArea(
        lastAddedIndex, data[lastAddedIndex],
        j, data[j],
        data.length - 1, data[data.length - 1]
      )

      if (area > maxArea) {
        maxArea = area
        maxAreaIndex = j
      }
    }

    if (maxAreaIndex >= 0) {
      result.push(data[maxAreaIndex])
      lastAddedIndex = maxAreaIndex
    }
  }

  for (const peak of peaks) {
    if (peak.index > 0 && peak.index < data.length - 1) {
      result.push(data[peak.index])
    }
  }

  result.push(data[data.length - 1])

  result.sort((a, b) => {
    const aIndex = data.indexOf(a)
    const bIndex = data.indexOf(b)
    return aIndex - bIndex
  })

  return result
}

function findPeaks(data) {
  const peaks = []
  const windowSize = Math.max(5, Math.floor(data.length / 100))

  for (let i = windowSize; i < data.length - windowSize; i++) {
    const current = data[i].close || data[i].value || data[i]
    let isPeak = true
    let isValley = true

    for (let j = i - windowSize; j <= i + windowSize; j++) {
      if (j === i) continue
      const compare = data[j].close || data[j].value || data[j]

      if (current < compare) isPeak = false
      if (current > compare) isValley = false
    }

    if (isPeak || isValley) {
      peaks.push({ index: i, isPeak, value: current })
    }
  }

  return peaks
}

function calculateTriangleArea(ax, ay, bx, by, cx, cy) {
  const ayVal = ay.close || ay.value || ay
  const byVal = by.close || by.value || by
  const cyVal = cy.close || cy.value || cy

  return Math.abs((ax - cx) * (byVal - ayVal) - (bx - ax) * (cyVal - ayVal))
}

export function getDownsampleThreshold(containerWidth, pixelPerPoint = 3) {
  return Math.max(100, Math.floor(containerWidth / pixelPerPoint))
}
