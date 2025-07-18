import Confetti from "react-confetti";
import { useWindowSize } from "react-use";

const CelebrationOverlay = ({ active }) => {
	const { width, height } = useWindowSize();

	if (!active) return null;

	return <Confetti width={width} height={height} />;
};

export default CelebrationOverlay;
