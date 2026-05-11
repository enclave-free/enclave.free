import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cx(...classes: ClassValue[]) {
  return twMerge(clsx(...classes))
}
