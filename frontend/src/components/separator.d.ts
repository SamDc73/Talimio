import type { ComponentPropsWithoutRef, ElementRef } from 'react';
import type * as SeparatorPrimitive from '@radix-ui/react-separator';

export interface SeparatorProps extends ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root> {
  className?: string;
  orientation?: 'horizontal' | 'vertical';
  decorative?: boolean;
}

declare const Separator: React.ForwardRefExoticComponent<
  SeparatorProps & React.RefAttributes<ElementRef<typeof SeparatorPrimitive.Root>>
>;

export { Separator };
