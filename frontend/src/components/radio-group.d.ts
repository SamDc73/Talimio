import type { ComponentPropsWithoutRef, ElementRef } from 'react';
import type * as RadioGroupPrimitive from '@radix-ui/react-radio-group';

export interface RadioGroupProps extends ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root> {
  className?: string;
}

export interface RadioGroupItemProps extends ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Item> {
  className?: string;
}

declare const RadioGroup: React.ForwardRefExoticComponent<
  RadioGroupProps & React.RefAttributes<ElementRef<typeof RadioGroupPrimitive.Root>>
>;

declare const RadioGroupItem: React.ForwardRefExoticComponent<
  RadioGroupItemProps & React.RefAttributes<ElementRef<typeof RadioGroupPrimitive.Item>>
>;

export { RadioGroup, RadioGroupItem };
