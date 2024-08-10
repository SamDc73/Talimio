/**
 * Breadcrumb Navigation Component
 *
 * Provides hierarchical navigation breadcrumbs for the course structure
 */

import { ChevronRight, Home } from "lucide-react"
import { Link } from "react-router-dom"

import { useBreadcrumbNavigation } from "../../utils/navigationUtils"

const Breadcrumbs = ({
	courseData = null,
	moduleData = null,
	lessonData = null,
	className = "",
	showHome = true,
	separator = "chevron", // "chevron" | "slash" | "arrow"
}) => {
	const { generateBreadcrumbs } = useBreadcrumbNavigation()

	const breadcrumbs = generateBreadcrumbs(courseData, moduleData, lessonData)

	// Don't render if only home breadcrumb and showHome is false
	if (!showHome && breadcrumbs.length === 1) {
		return null
	}

	// Don't render if no meaningful breadcrumbs
	if (breadcrumbs.length === 0 || (breadcrumbs.length === 1 && !showHome)) {
		return null
	}

	const getSeparatorIcon = () => {
		switch (separator) {
			case "slash":
				return <span className="text-gray-400">/</span>
			case "arrow":
				return <span className="text-gray-400">→</span>
			default:
				return <ChevronRight className="h-4 w-4 text-gray-400" />
		}
	}

	return (
		<nav className={`flex items-center space-x-2 text-sm ${className}`} aria-label="Breadcrumb navigation">
			<ol className="flex items-center space-x-2">
				{breadcrumbs.map((breadcrumb, index) => {
					const isLast = index === breadcrumbs.length - 1
					const isHome = breadcrumb.path === "/"

					// Skip home if showHome is false
					if (!showHome && isHome) {
						return null
					}

					return (
						<li key={breadcrumb.path} className="flex items-center">
							{/* Separator */}
							{index > 0 && (!isHome || showHome) && <span className="mx-2 flex-shrink-0">{getSeparatorIcon()}</span>}

							{/* Breadcrumb item */}
							{isLast || breadcrumb.isActive ? (
								<span
									className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-[200px]"
									title={breadcrumb.label}
									aria-current="page"
								>
									{isHome ? <Home className="h-4 w-4" /> : breadcrumb.label}
								</span>
							) : (
								<Link
									to={breadcrumb.path}
									className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors truncate max-w-[200px] flex items-center"
									title={breadcrumb.label}
								>
									{isHome ? <Home className="h-4 w-4" /> : breadcrumb.label}
								</Link>
							)}
						</li>
					)
				})}
			</ol>
		</nav>
	)
}

// Compact version for headers
export const CompactBreadcrumbs = ({ courseData, moduleData, lessonData, className = "" }) => {
	return (
		<Breadcrumbs
			courseData={courseData}
			moduleData={moduleData}
			lessonData={lessonData}
			className={`text-xs ${className}`}
			showHome={false}
			separator="chevron"
		/>
	)
}

// Full version for page content
export const FullBreadcrumbs = ({ courseData, moduleData, lessonData, className = "" }) => {
	return (
		<div className={`bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-2 ${className}`}>
			<Breadcrumbs
				courseData={courseData}
				moduleData={moduleData}
				lessonData={lessonData}
				showHome={true}
				separator="chevron"
			/>
		</div>
	)
}

export default Breadcrumbs
