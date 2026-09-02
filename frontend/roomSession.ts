import type {
    CardDeck,
    CardItem,
    MatchItem
} from "./types"

export interface RoomSessionState {
    cardDeck: CardDeck
    swipeHistory: CardDeck
    matchFound: boolean
    matchItem: MatchItem
    roomReady: boolean
    genre: string
    hideWatched: boolean
    lastError: string | null
}

export const EMPTY_MATCH_ITEM: MatchItem = {
    title: null, posterUrl: null, mediaId: null, mediaType: null, 
    deepLink: null, rating: null, duration: null, year: null
}

export const initialRoomSessionState: RoomSessionState = {
    cardDeck: [],
    swipeHistory: [],
    matchFound: false,
    matchItem: EMPTY_MATCH_ITEM,
    roomReady: false,
    genre: "All",
    hideWatched: false,
    lastError: null
}

export type RoomSessionAction = 
    | { type: "DECK_LOADED"; deck: CardDeck }
    | { type: "SWIPE_SUCCEEDED"; card: CardItem }
    | { type: "UNDO_SUCCEEDED"; card: CardItem}
    | { type: "GENRE_SELECTED"; genre: string }
    | { type: "GENRE_COMMAND_SUCCEEDED"; deck: CardDeck; mutationEventId: number }
    | { type: "HIDE_WATCHED_COMMAND_SUCCEEDED"; deck: CardDeck; hideWatched: boolean; mutationEventId: number }
    | { type: "MATCH_FOUND"; matchItem: MatchItem }
    | { type: "MATCH_DISMISSED" }
    | { type: "SSE_SESSION_BOOTSTRAP"; ready: boolean }
    | { type: "SSE_SESSION_READY" }
    | { type: "SSE_SESSION_CLOSED" }
    | { type: "SSE_GENRE_CHANGED"; genre?: string }
    | { type: "SSE_HIDE_WATCHED_CHANGED"; hideWatched?: boolean }
    | { type: "COMMAND_FAILED"; message: string }
    | { type: "SESSION_ENDED" }


export function roomSessionReducer(
    state: RoomSessionState,
    action: RoomSessionAction
): RoomSessionState {
    switch (action.type) {
        case "DECK_LOADED":
            return { ...state, cardDeck: action.deck, swipeHistory: [] }
        case "SWIPE_SUCCEEDED":
            return {
                ...state,
                cardDeck: state.cardDeck.slice(1),
                swipeHistory: [...state.swipeHistory, action.card],
                lastError: null
            }
        case "UNDO_SUCCEEDED":
            return {
                ...state,
                cardDeck: [action.card, ...state.cardDeck],
                swipeHistory: state.swipeHistory.slice(0, -1),
                lastError: null
            }
        case "GENRE_SELECTED":
            return { ...state, genre: action.genre}
        case "GENRE_COMMAND_SUCCEEDED":
            return {
                ...state,
                cardDeck: action.deck,
                swipeHistory: [],
                lastError: null
            }
        case "HIDE_WATCHED_COMMAND_SUCCEEDED":
            return {
                ...state,
                cardDeck: action.deck,
                swipeHistory: [],
                hideWatched: action.hideWatched,
                lastError: null
            }
        case "MATCH_FOUND":
            return { ...state, matchFound: true, matchItem: action.matchItem }
        case "MATCH_DISMISSED":
            return { ...state, matchFound: false }
        case "SSE_SESSION_BOOTSTRAP":
            return { ...state, roomReady: action.ready }
        case "SSE_SESSION_READY":
            return { ...state, roomReady: true }
        case "SSE_SESSION_CLOSED":
            return { ...state, roomReady: false }
        case "SSE_GENRE_CHANGED":
            return { ...state, genre: action.genre ?? state.genre }
        case "SSE_HIDE_WATCHED_CHANGED":
            return { ...state, hideWatched: action.hideWatched ?? state.hideWatched }
        case "COMMAND_FAILED":
            return { ...state, lastError: action.message }
        case "SESSION_ENDED":
            return {
                ...state,
                roomReady: false,
                hideWatched: false,
                cardDeck: [],
                swipeHistory: [],
                matchFound: false,
                matchItem: EMPTY_MATCH_ITEM,
                lastError: null
            }
        default: {
            const _exhaustive: never = action
            return _exhaustive
        }
    }
}