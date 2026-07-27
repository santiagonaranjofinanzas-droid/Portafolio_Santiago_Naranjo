export type AiIntent = {
  focus: string
  prompt: string
}

export type AiSeed = AiIntent & {
  id: number
}

export type AiChatMessage = {
  role: 'user'  'assistant'
  content: string
}