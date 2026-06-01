import java.util.*;

/**
 * Builder Design Pattern - Complete Implementation
 * 
 * Separates the construction of a complex object from its representation,
 * allowing the same construction process to create different representations.
 */

// ============================================================
// APPROACH 1: Classic Builder Pattern (with Director)
// ============================================================

// Product
class House {
    private String foundation;
    private String structure;
    private String roof;
    private String interior;
    private int floors;
    private boolean hasGarage;
    private boolean hasSwimmingPool;
    private boolean hasGarden;

    public void setFoundation(String foundation) { this.foundation = foundation; }
    public void setStructure(String structure) { this.structure = structure; }
    public void setRoof(String roof) { this.roof = roof; }
    public void setInterior(String interior) { this.interior = interior; }
    public void setFloors(int floors) { this.floors = floors; }
    public void setHasGarage(boolean hasGarage) { this.hasGarage = hasGarage; }
    public void setHasSwimmingPool(boolean hasSwimmingPool) { this.hasSwimmingPool = hasSwimmingPool; }
    public void setHasGarden(boolean hasGarden) { this.hasGarden = hasGarden; }

    @Override
    public String toString() {
        return String.format("House [foundation=%s, structure=%s, roof=%s, interior=%s, " +
                "floors=%d, garage=%b, pool=%b, garden=%b]",
                foundation, structure, roof, interior, floors, hasGarage, hasSwimmingPool, hasGarden);
    }
}

// Builder Interface
interface HouseBuilder {
    HouseBuilder buildFoundation();
    HouseBuilder buildStructure();
    HouseBuilder buildRoof();
    HouseBuilder buildInterior();
    HouseBuilder buildFloors();
    HouseBuilder addGarage();
    HouseBuilder addSwimmingPool();
    HouseBuilder addGarden();
    House getResult();
}

// Concrete Builder 1
class ModernHouseBuilder implements HouseBuilder {
    private House house = new House();

    public HouseBuilder buildFoundation() { house.setFoundation("Concrete slab"); return this; }
    public HouseBuilder buildStructure() { house.setStructure("Steel and glass"); return this; }
    public HouseBuilder buildRoof() { house.setRoof("Flat green roof"); return this; }
    public HouseBuilder buildInterior() { house.setInterior("Minimalist open-plan"); return this; }
    public HouseBuilder buildFloors() { house.setFloors(2); return this; }
    public HouseBuilder addGarage() { house.setHasGarage(true); return this; }
    public HouseBuilder addSwimmingPool() { house.setHasSwimmingPool(true); return this; }
    public HouseBuilder addGarden() { house.setHasGarden(true); return this; }
    public House getResult() { return house; }
}

// Concrete Builder 2
class VictorianHouseBuilder implements HouseBuilder {
    private House house = new House();

    public HouseBuilder buildFoundation() { house.setFoundation("Brick and stone"); return this; }
    public HouseBuilder buildStructure() { house.setStructure("Wood and brick"); return this; }
    public HouseBuilder buildRoof() { house.setRoof("Steep pitched with ornate trim"); return this; }
    public HouseBuilder buildInterior() { house.setInterior("Ornate with crown molding"); return this; }
    public HouseBuilder buildFloors() { house.setFloors(3); return this; }
    public HouseBuilder addGarage() { house.setHasGarage(true); return this; }
    public HouseBuilder addSwimmingPool() { house.setHasSwimmingPool(false); return this; }
    public HouseBuilder addGarden() { house.setHasGarden(true); return this; }
    public House getResult() { return house; }
}

// Director - orchestrates building steps
class HouseDirector {
    public House constructLuxuryHouse(HouseBuilder builder) {
        return builder.buildFoundation()
                .buildStructure()
                .buildRoof()
                .buildInterior()
                .buildFloors()
                .addGarage()
                .addSwimmingPool()
                .addGarden()
                .getResult();
    }

    public House constructSimpleHouse(HouseBuilder builder) {
        return builder.buildFoundation()
                .buildStructure()
                .buildRoof()
                .buildInterior()
                .buildFloors()
                .getResult();
    }
}

// ============================================================
// APPROACH 2: Fluent Builder (Inner static class pattern)
// Used for immutable objects with many optional parameters
// ============================================================

class HttpRequest {
    // All fields are final - immutable object
    private final String method;
    private final String url;
    private final Map<String, String> headers;
    private final String body;
    private final int timeout;
    private final boolean followRedirects;
    private final String contentType;

    private HttpRequest(Builder builder) {
        this.method = builder.method;
        this.url = builder.url;
        this.headers = Collections.unmodifiableMap(builder.headers);
        this.body = builder.body;
        this.timeout = builder.timeout;
        this.followRedirects = builder.followRedirects;
        this.contentType = builder.contentType;
    }

    @Override
    public String toString() {
        return String.format("HttpRequest [%s %s, contentType=%s, timeout=%dms, " +
                "followRedirects=%b, headers=%s, body=%s]",
                method, url, contentType, timeout, followRedirects, headers, 
                body != null ? body.substring(0, Math.min(body.length(), 50)) : "null");
    }

    // Static inner Builder class
    public static class Builder {
        // Required parameters
        private final String method;
        private final String url;

        // Optional parameters with defaults
        private Map<String, String> headers = new HashMap<>();
        private String body = null;
        private int timeout = 30000;
        private boolean followRedirects = true;
        private String contentType = "application/json";

        public Builder(String method, String url) {
            this.method = method;
            this.url = url;
        }

        public Builder header(String key, String value) {
            this.headers.put(key, value);
            return this;
        }

        public Builder body(String body) {
            this.body = body;
            return this;
        }

        public Builder timeout(int timeoutMs) {
            this.timeout = timeoutMs;
            return this;
        }

        public Builder followRedirects(boolean follow) {
            this.followRedirects = follow;
            return this;
        }

        public Builder contentType(String contentType) {
            this.contentType = contentType;
            return this;
        }

        public HttpRequest build() {
            // Validation before building
            if (url == null || url.isEmpty()) {
                throw new IllegalStateException("URL cannot be empty");
            }
            if (method == null || method.isEmpty()) {
                throw new IllegalStateException("Method cannot be empty");
            }
            return new HttpRequest(this);
        }
    }
}

// ============================================================
// APPROACH 3: Generic Query Builder (another real-world example)
// ============================================================

class SqlQuery {
    private final String query;

    private SqlQuery(String query) { this.query = query; }
    public String getQuery() { return query; }

    @Override
    public String toString() { return query; }

    public static class Builder {
        private String table;
        private List<String> columns = new ArrayList<>();
        private List<String> conditions = new ArrayList<>();
        private String orderBy;
        private Integer limit;

        public Builder select(String... cols) {
            columns.addAll(Arrays.asList(cols));
            return this;
        }

        public Builder from(String table) {
            this.table = table;
            return this;
        }

        public Builder where(String condition) {
            conditions.add(condition);
            return this;
        }

        public Builder orderBy(String column) {
            this.orderBy = column;
            return this;
        }

        public Builder limit(int limit) {
            this.limit = limit;
            return this;
        }

        public SqlQuery build() {
            StringBuilder sb = new StringBuilder("SELECT ");
            sb.append(columns.isEmpty() ? "*" : String.join(", ", columns));
            sb.append(" FROM ").append(table);
            if (!conditions.isEmpty()) {
                sb.append(" WHERE ").append(String.join(" AND ", conditions));
            }
            if (orderBy != null) sb.append(" ORDER BY ").append(orderBy);
            if (limit != null) sb.append(" LIMIT ").append(limit);
            return new SqlQuery(sb.toString());
        }
    }
}

// ============================================================
// Main - Demonstration
// ============================================================

public class BuilderPattern {
    public static void main(String[] args) {
        System.out.println("=== BUILDER DESIGN PATTERN ===\n");

        // --- Classic Builder with Director ---
        System.out.println("--- 1. Classic Builder with Director ---");
        HouseDirector director = new HouseDirector();

        House modernLuxury = director.constructLuxuryHouse(new ModernHouseBuilder());
        System.out.println("Modern Luxury: " + modernLuxury);

        House victorianSimple = director.constructSimpleHouse(new VictorianHouseBuilder());
        System.out.println("Victorian Simple: " + victorianSimple);

        // Builder without director (client controls steps)
        House custom = new ModernHouseBuilder()
                .buildFoundation()
                .buildStructure()
                .buildRoof()
                .addSwimmingPool()
                .getResult();
        System.out.println("Custom (no director): " + custom);

        // --- Fluent Builder (HTTP Request) ---
        System.out.println("\n--- 2. Fluent Builder (HttpRequest) ---");
        HttpRequest getRequest = new HttpRequest.Builder("GET", "https://api.example.com/users")
                .header("Authorization", "Bearer token123")
                .header("Accept", "application/json")
                .timeout(5000)
                .build();
        System.out.println(getRequest);

        HttpRequest postRequest = new HttpRequest.Builder("POST", "https://api.example.com/users")
                .contentType("application/json")
                .body("{\"name\": \"John\", \"email\": \"john@example.com\"}")
                .header("Authorization", "Bearer token123")
                .followRedirects(false)
                .timeout(10000)
                .build();
        System.out.println(postRequest);

        // --- SQL Query Builder ---
        System.out.println("\n--- 3. SQL Query Builder ---");
        SqlQuery query = new SqlQuery.Builder()
                .select("name", "email", "age")
                .from("users")
                .where("age > 18")
                .where("active = true")
                .orderBy("name ASC")
                .limit(10)
                .build();
        System.out.println(query);

        SqlQuery simpleQuery = new SqlQuery.Builder()
                .from("products")
                .where("price < 100")
                .build();
        System.out.println(simpleQuery);
    }
}
