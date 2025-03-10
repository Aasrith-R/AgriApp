from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class EmissionFactor:
    value: float
    unit: str
    description: str

class FarmCarbonFootprint:
    "#Calculate and track carbon footprint for farming activities."""

    def __init__(self):
        self.emission_factors = {
            "diesel": EmissionFactor(2.68, "kg CO2/L", "Diesel fuel consumption"),
            "gasoline": EmissionFactor(2.31, "kg CO2/L", "Gasoline fuel consumption"),
            "electricity": EmissionFactor(0.92, "kg CO2/kWh", "Electricity usage"),
            "fertilizer": EmissionFactor(1.5, "kg CO2/kg", "Synthetic fertilizer use"),
            "livestock": EmissionFactor(50.0, "kg CO2/head", "Livestock emissions")
        }
        self.activities = {}

    def add_activity(self, activity: str, amount: float) -> bool:
    
        if not isinstance(amount, (int, float)) or amount < 0:
            print(f"Invalid amount: {amount}. Must be a positive number.")
            return False

        if activity not in self.emission_factors:
            print(f"Unknown activity: {activity}. Valid activities are: {list(self.emission_factors.keys())}")
            return False

        self.activities[activity] = self.activities.get(activity, 0) + amount
        return True

    def calculate_footprint(self) -> Dict[str, float]:
        """
        Calculate emissions for all tracked activities and eturns:
            Dictionary mapping activities to their emissions in kg CO2
        """
        return {
            activity: amount * self.emission_factors[activity].value
            for activity, amount in self.activities.items()
        }

    def get_total_emissions(self) -> float:
        """Calculate total emissions across all activities."""
        return sum(self.calculate_footprint().values())

    def get_recommendations(self) -> List[str]:
        """Generate recommendations for reducing emissions."""
        recommendations = []
        footprint = self.calculate_footprint()
        
        # Sort activities by emission amount to focus on biggest contributors
        sorted_activities = sorted(
            footprint.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for activity, emissions in sorted_activities:
            if activity == "diesel" or activity == "gasoline":
                recommendations.append(
                    f"Consider reducing {activity} usage ({emissions:.1f} kg CO2) "
                    "by optimizing vehicle routes or switching to electric vehicles."
                )
            elif activity == "electricity":
                recommendations.append(
                    f"Reduce electricity emissions ({emissions:.1f} kg CO2) "
                    "by using energy-efficient equipment or solar power."
                )
            elif activity == "fertilizer":
                recommendations.append(
                    f"Consider reducing synthetic fertilizer use ({emissions:.1f} kg CO2) "
                    "by implementing crop rotation or using organic alternatives."
                )

        return recommendations

