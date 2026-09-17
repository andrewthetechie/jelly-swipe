import type { JSX } from "react"

interface FormErrorProps {
    message: string
}

export default function FormError({ message }: FormErrorProps): JSX.Element {
    return (
        <p className="form-error" role="alert">{message}</p>
    )
}
