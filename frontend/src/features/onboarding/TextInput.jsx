import { Input } from "@/components/input";

export const TextInput = ({ value, onChange, placeholder }) => (
	<Input
		value={value}
		onChange={(e) => onChange(e.target.value)}
		placeholder={placeholder}
		className="w-full"
	/>
);
