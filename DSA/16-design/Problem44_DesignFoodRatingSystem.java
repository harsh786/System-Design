import java.util.*;

/**
 * Problem 44: Design Food Rating System
 * 
 * API Contract:
 * - changeRating(food, newRating): Update food's rating
 * - highestRated(cuisine): Return highest-rated food in cuisine (lex smallest on tie)
 * 
 * Complexity: changeRating O(log n), highestRated O(1)
 * Data Structure: HashMap + TreeSet per cuisine (sorted by rating desc, name asc)
 * 
 * Production Analogy: Restaurant recommendation engines, product rating systems,
 * app store rankings, content recommendation by category
 */
public class Problem44_DesignFoodRatingSystem {

    static class FoodRatings {
        private Map<String, Integer> foodToRating;
        private Map<String, String> foodToCuisine;
        private Map<String, TreeSet<String>> cuisineToFoods;

        public FoodRatings(String[] foods, String[] cuisines, int[] ratings) {
            foodToRating = new HashMap<>();
            foodToCuisine = new HashMap<>();
            cuisineToFoods = new HashMap<>();

            for (int i = 0; i < foods.length; i++) {
                foodToRating.put(foods[i], ratings[i]);
                foodToCuisine.put(foods[i], cuisines[i]);
                cuisineToFoods.computeIfAbsent(cuisines[i], k -> new TreeSet<>((a, b) -> {
                    int diff = foodToRating.get(b) - foodToRating.get(a);
                    return diff != 0 ? diff : a.compareTo(b);
                })).add(foods[i]);
            }
        }

        public void changeRating(String food, int newRating) {
            String cuisine = foodToCuisine.get(food);
            TreeSet<String> set = cuisineToFoods.get(cuisine);
            set.remove(food);
            foodToRating.put(food, newRating);
            set.add(food);
        }

        public String highestRated(String cuisine) {
            return cuisineToFoods.get(cuisine).first();
        }
    }

    public static void main(String[] args) {
        FoodRatings fr = new FoodRatings(
            new String[]{"kimchi", "miso", "sushi", "moussaka", "ramen", "bulgogi"},
            new String[]{"korean", "japanese", "japanese", "greek", "japanese", "korean"},
            new int[]{9, 12, 8, 15, 14, 7}
        );
        assert fr.highestRated("korean").equals("kimchi");
        assert fr.highestRated("japanese").equals("ramen");
        fr.changeRating("sushi", 16);
        assert fr.highestRated("japanese").equals("sushi");
        fr.changeRating("ramen", 16);
        assert fr.highestRated("japanese").equals("ramen"); // lex smaller

        System.out.println("All tests passed!");
    }
}
