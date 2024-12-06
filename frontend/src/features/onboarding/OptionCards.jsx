import React from 'react';

import { Card, CardContent } from "@/components/card"; 

export const OptionCards = ({ options, value, onChange }) => (
  <div className="grid gap-2">
    {options.map((option) => (
      <Card
        key={option}
        className={`cursor-pointer transition-colors hover:bg-muted ${
          value === option ? 'border-primary' : ''
        }`}
        onClick={() => onChange(option)}
      >
        <CardContent className="p-4">
          {option}
        </CardContent>
      </Card>
    ))}
  </div>
);
