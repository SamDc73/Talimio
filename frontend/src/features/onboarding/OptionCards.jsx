import React from "react";

import { Card, CardContent } from "@/components/card";

export const OptionCards = ({ options, value, onChange }) => (
  <div className="grid gap-2">
    {options.map((option, idx) => (
      // Using a combination of option and index as the key to avoid duplicate key warning
      <Card
        key={option.id || option}
        className={`cursor-pointer transition-colors hover:bg-muted ${value === option ? "border-primary" : ""}`}
        onClick={() => onChange(option)}
      >
        <CardContent className="p-4">{option}</CardContent>
      </Card>
    ))}
  </div>
);
