// Module-private blob storage — replaces unsafe window.__voiceover_* globals
let videoBlob: Blob | null = null;
let audioBlob: Blob | null = null;

export const blobStore = {
	setVideo(b: Blob) { videoBlob = b; },
	getVideo() { return videoBlob; },
	setAudio(b: Blob) { audioBlob = b; },
	getAudio() { return audioBlob; },
	clear() { videoBlob = null; audioBlob = null; },
};
