import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

export type SpeechToTextErrorCode = 'not-allowed' | 'no-speech' | 'network' | 'unknown'

const resolveSpeechRecognitionCtor = (): SpeechRecognitionConstructor | undefined =>
  typeof window === 'undefined'
    ? undefined
    : (window.SpeechRecognition ?? window.webkitSpeechRecognition)

const localeToSpeechLang = (locale: string): string =>
  locale.startsWith('pl') ? 'pl-PL' : 'en-US'

const mapErrorCode = (code: string): SpeechToTextErrorCode => {
  if (code === 'not-allowed' || code === 'service-not-allowed') return 'not-allowed'
  if (code === 'no-speech') return 'no-speech'
  if (code === 'network') return 'network'
  return 'unknown'
}

export function useSpeechToText(onFinalTranscript: (text: string) => void) {
  const { locale } = useI18n()
  const SpeechRecognitionCtor = resolveSpeechRecognitionCtor()

  const isSupported = computed(() => !!SpeechRecognitionCtor)
  const isListening = ref(false)
  const interimTranscript = ref('')
  const error = ref<SpeechToTextErrorCode | null>(null)

  let recognition: SpeechRecognition | null = null

  const stop = () => {
    recognition?.stop()
  }

  const start = () => {
    if (!SpeechRecognitionCtor || isListening.value) return

    error.value = null
    interimTranscript.value = ''

    recognition = new SpeechRecognitionCtor()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = localeToSpeechLang(locale.value)

    recognition.onresult = (event) => {
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results.item(i)
        const transcript = result.item(0)?.transcript ?? ''
        if (result.isFinal) {
          onFinalTranscript(transcript)
        } else {
          interim += transcript
        }
      }
      interimTranscript.value = interim
    }

    recognition.onerror = (event) => {
      error.value = mapErrorCode(event.error)
    }

    recognition.onend = () => {
      isListening.value = false
      interimTranscript.value = ''
      recognition = null
    }

    recognition.start()
    isListening.value = true
  }

  onUnmounted(() => {
    recognition?.abort()
  })

  return { isSupported, isListening, interimTranscript, error, start, stop }
}
