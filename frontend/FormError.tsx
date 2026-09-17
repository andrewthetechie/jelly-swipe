import type { JSX } from "react"

interface FormErrorProps {
    message: string | null
}

export default function FormError({ message }: FormErrorProps): JSX.Element | null {
    if (!message) {
        return null
    }
    return <p className="form-error" role="alert">{message}</p>
}
