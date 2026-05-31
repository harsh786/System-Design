# Staff Engineer - Part 5: System Design Coding Problems in Java
# Actual design + code questions asked at FAANG for Staff/Principal level

## Design Problem 1: Design a Distributed Rate Limiter Service

**Asked at:** Google, Uber, Stripe (Staff level)

```java
// Requirements:
// - 1000 requests/sec per user across multiple instances
// - Low latency (<5ms decision time)
// - Handle clock skew between instances
// - Graceful degradation if Redis is down

interface RateLimiter {
    boolean isAllowed(String clientId, int maxRequests, Duration window);
}

// SLIDING WINDOW LOG (Redis-based, distributed)
class DistributedSlidingWindowRateLimiter implements RateLimiter {
    private final RedisTemplate<String, String> redis;
    private final Cache<String, AtomicInteger> localFallback;  // If Redis down
    
    @Override
    public boolean isAllowed(String clientId, int maxRequests, Duration window) {
        String key = "ratelimit:" + clientId;
        long now = System.currentTimeMillis();
        long windowStart = now - window.toMillis();
        
        // Lua script for atomicity (single Redis roundtrip!)
        String luaScript = """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_start = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            local window_ms = tonumber(ARGV[4])
            
            -- Remove expired entries
            redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
            
            -- Count current requests in window
            local count = redis.call('ZCARD', key)
            
            if count < max_requests then
                -- Add this request
                redis.call('ZADD', key, now, now .. ':' .. math.random())
                redis.call('PEXPIRE', key, window_ms)
                return 1  -- Allowed
            else
                return 0  -- Rejected
            end
            """;
        
        try {
            Long result = redis.execute(new DefaultRedisScript<>(luaScript, Long.class),
                List.of(key),
                String.valueOf(now), String.valueOf(windowStart),
                String.valueOf(maxRequests), String.valueOf(window.toMillis()));
            return result != null && result == 1;
        } catch (Exception e) {
            // Redis down → fall back to local rate limiting (degraded mode)
            return localFallback(clientId, maxRequests);
        }
    }
    
    private boolean localFallback(String clientId, int maxRequests) {
        AtomicInteger counter = localFallback.get(clientId, k -> new AtomicInteger(0));
        return counter.incrementAndGet() <= maxRequests;
    }
}

// TOKEN BUCKET (Redis, better for bursty traffic):
class DistributedTokenBucket implements RateLimiter {
    @Override
    public boolean isAllowed(String clientId, int maxTokens, Duration refillPeriod) {
        String luaScript = """
            local key = KEYS[1]
            local max_tokens = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            
            local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
            local tokens = tonumber(bucket[1]) or max_tokens
            local last_refill = tonumber(bucket[2]) or now
            
            -- Refill tokens
            local elapsed = (now - last_refill) / 1000.0
            tokens = math.min(max_tokens, tokens + elapsed * refill_rate)
            
            if tokens >= 1 then
                tokens = tokens - 1
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('PEXPIRE', key, 60000)
                return 1
            else
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('PEXPIRE', key, 60000)
                return 0
            end
            """;
        
        double refillRate = (double) maxTokens / refillPeriod.getSeconds();
        Long result = redis.execute(new DefaultRedisScript<>(luaScript, Long.class),
            List.of("bucket:" + clientId),
            String.valueOf(maxTokens), String.valueOf(refillRate),
            String.valueOf(System.currentTimeMillis()));
        return result != null && result == 1;
    }
}
```

---

## Design Problem 2: Design a Distributed Job Scheduler

**Asked at:** Amazon, Google, LinkedIn (Staff level)

```java
// Requirements:
// - Schedule jobs for future execution (one-time or recurring)
// - At-least-once execution guarantee
// - No duplicate execution (exactly-once best effort)
// - Horizontal scalability
// - Handle worker failures

class DistributedJobScheduler {
    private final DataSource db;
    private final ScheduledExecutorService poller;
    private final ExecutorService workerPool;
    private final String instanceId = UUID.randomUUID().toString();
    
    // Job table:
    // id, payload, scheduled_at, status (PENDING/RUNNING/COMPLETED/FAILED),
    // locked_by, locked_at, retry_count, max_retries, cron_expression
    
    void start() {
        // Poll for due jobs every second
        poller.scheduleAtFixedRate(this::pollAndExecute, 0, 1, TimeUnit.SECONDS);
    }
    
    void scheduleJob(Job job) {
        // INSERT INTO jobs (id, payload, scheduled_at, status)
        // VALUES (?, ?, ?, 'PENDING')
        jobRepository.save(job);
    }
    
    void pollAndExecute() {
        // Optimistic locking: Claim jobs that are due
        // UPDATE jobs SET status='RUNNING', locked_by=?, locked_at=NOW()
        // WHERE status='PENDING' AND scheduled_at <= NOW()
        // AND (locked_by IS NULL OR locked_at < NOW() - INTERVAL '5 minutes')
        // LIMIT 10
        List<Job> claimed = jobRepository.claimDueJobs(instanceId, 10);
        
        for (Job job : claimed) {
            workerPool.submit(() -> executeJob(job));
        }
    }
    
    void executeJob(Job job) {
        try {
            JobHandler handler = handlerRegistry.get(job.getType());
            handler.execute(job.getPayload());
            
            if (job.getCronExpression() != null) {
                // Recurring: schedule next execution
                Instant nextRun = cronParser.nextExecution(job.getCronExpression());
                jobRepository.reschedule(job.getId(), nextRun);
            } else {
                jobRepository.markCompleted(job.getId());
            }
        } catch (Exception e) {
            if (job.getRetryCount() < job.getMaxRetries()) {
                // Exponential backoff retry
                Duration delay = Duration.ofSeconds((long) Math.pow(2, job.getRetryCount()));
                jobRepository.scheduleRetry(job.getId(), Instant.now().plus(delay));
            } else {
                jobRepository.markFailed(job.getId(), e.getMessage());
                // Alert / dead letter queue
            }
        }
    }
    
    // Heartbeat: detect dead workers
    @Scheduled(fixedRate = 30000)
    void detectDeadWorkers() {
        // UPDATE jobs SET status='PENDING', locked_by=NULL
        // WHERE status='RUNNING' AND locked_at < NOW() - INTERVAL '5 minutes'
        jobRepository.releaseStaleJobs(Duration.ofMinutes(5));
    }
}
```

---

## Design Problem 3: Design an In-Memory Event Store (Event Sourcing)

**Asked at:** Goldman Sachs, Amazon, Confluent

```java
class InMemoryEventStore {
    // Per-aggregate event streams
    private final ConcurrentHashMap<String, List<DomainEvent>> streams = new ConcurrentHashMap<>();
    private final ReadWriteLock globalLock = new ReentrantReadWriteLock();
    private final Map<String, List<EventHandler>> subscribers = new ConcurrentHashMap<>();
    
    // Append events to aggregate's stream (optimistic concurrency)
    void append(String aggregateId, List<DomainEvent> events, int expectedVersion) {
        globalLock.writeLock().lock();
        try {
            List<DomainEvent> stream = streams.computeIfAbsent(aggregateId, 
                k -> new CopyOnWriteArrayList<>());
            
            // Optimistic concurrency check
            if (stream.size() != expectedVersion) {
                throw new ConcurrencyException(
                    "Expected version " + expectedVersion + " but was " + stream.size());
            }
            
            // Assign version numbers and timestamps
            int version = expectedVersion;
            for (DomainEvent event : events) {
                event.setVersion(++version);
                event.setTimestamp(Instant.now());
                stream.add(event);
            }
        } finally {
            globalLock.writeLock().unlock();
        }
        
        // Publish to subscribers (outside lock!)
        for (DomainEvent event : events) {
            publishToSubscribers(event);
        }
    }
    
    // Load aggregate's event stream
    List<DomainEvent> loadStream(String aggregateId) {
        globalLock.readLock().lock();
        try {
            return List.copyOf(streams.getOrDefault(aggregateId, List.of()));
        } finally {
            globalLock.readLock().unlock();
        }
    }
    
    // Load from specific version (for partial replay)
    List<DomainEvent> loadStreamFrom(String aggregateId, int fromVersion) {
        List<DomainEvent> stream = loadStream(aggregateId);
        return stream.stream()
            .filter(e -> e.getVersion() > fromVersion)
            .collect(Collectors.toList());
    }
    
    // Rebuild aggregate state
    <T extends Aggregate> T loadAggregate(String id, Supplier<T> factory) {
        T aggregate = factory.get();
        List<DomainEvent> events = loadStream(id);
        for (DomainEvent event : events) {
            aggregate.apply(event);
        }
        aggregate.setVersion(events.size());
        return aggregate;
    }
    
    // Snapshot for performance (avoid replaying thousands of events)
    private final ConcurrentHashMap<String, Snapshot> snapshots = new ConcurrentHashMap<>();
    
    <T extends Aggregate> T loadAggregateWithSnapshot(String id, Supplier<T> factory) {
        Snapshot snapshot = snapshots.get(id);
        T aggregate;
        int fromVersion;
        
        if (snapshot != null) {
            aggregate = (T) snapshot.getState();
            fromVersion = snapshot.getVersion();
        } else {
            aggregate = factory.get();
            fromVersion = 0;
        }
        
        // Only replay events AFTER snapshot
        List<DomainEvent> events = loadStreamFrom(id, fromVersion);
        for (DomainEvent event : events) {
            aggregate.apply(event);
        }
        
        // Take new snapshot every 100 events
        if (events.size() > 100) {
            snapshots.put(id, new Snapshot(aggregate.copy(), aggregate.getVersion()));
        }
        
        return aggregate;
    }
}
```

---

## Design Problem 4: Design a Concurrent Web Crawler

**Asked at:** Google, Amazon, Microsoft (Staff level)

```java
class ConcurrentWebCrawler {
    private final int maxPages;
    private final Set<String> visited = ConcurrentHashMap.newKeySet();
    private final BlockingQueue<String> frontier = new LinkedBlockingQueue<>();
    private final ExecutorService executor;
    private final AtomicInteger pagesProcessed = new AtomicInteger(0);
    private final Phaser phaser = new Phaser(1);  // Dynamic registration
    
    ConcurrentWebCrawler(int maxPages, int threads) {
        this.maxPages = maxPages;
        this.executor = Executors.newFixedThreadPool(threads);
    }
    
    Set<String> crawl(String seedUrl) {
        frontier.offer(seedUrl);
        visited.add(seedUrl);
        
        // Launch worker threads
        int workers = 10;
        for (int i = 0; i < workers; i++) {
            executor.submit(this::worker);
        }
        
        // Wait for all work to complete
        phaser.arriveAndAwaitAdvance();
        executor.shutdown();
        return visited;
    }
    
    private void worker() {
        phaser.register();
        try {
            while (pagesProcessed.get() < maxPages) {
                String url = frontier.poll(1, TimeUnit.SECONDS);
                if (url == null) {
                    if (frontier.isEmpty()) break;  // No more work
                    continue;
                }
                
                try {
                    // Respect robots.txt and rate limiting
                    respectRateLimit(getDomain(url));
                    
                    // Fetch and parse
                    String html = fetchPage(url);
                    List<String> links = extractLinks(html, url);
                    
                    pagesProcessed.incrementAndGet();
                    
                    // Add new URLs to frontier
                    for (String link : links) {
                        if (visited.add(link) && pagesProcessed.get() < maxPages) {
                            frontier.offer(link);
                        }
                    }
                } catch (Exception e) {
                    // Log and continue (don't let one failure stop crawling)
                }
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            phaser.arriveAndDeregister();
        }
    }
    
    // Per-domain rate limiting (politeness)
    private final ConcurrentHashMap<String, Semaphore> domainLimits = new ConcurrentHashMap<>();
    
    private void respectRateLimit(String domain) throws InterruptedException {
        Semaphore limit = domainLimits.computeIfAbsent(domain, 
            d -> new Semaphore(2));  // Max 2 concurrent per domain
        limit.acquire();
        try {
            Thread.sleep(100);  // Min 100ms between requests to same domain
        } finally {
            limit.release();
        }
    }
}
```

---

## Design Problem 5: Design a Pub/Sub System with Message Ordering

**Asked at:** Google, LinkedIn, Confluent

```java
class OrderedPubSub {
    private final Map<String, Topic> topics = new ConcurrentHashMap<>();
    private final ExecutorService dispatchPool;
    
    OrderedPubSub(int threads) {
        this.dispatchPool = Executors.newFixedThreadPool(threads);
    }
    
    Topic createTopic(String name, int partitions) {
        Topic topic = new Topic(name, partitions);
        topics.put(name, topic);
        return topic;
    }
    
    void publish(String topicName, String partitionKey, Message message) {
        Topic topic = topics.get(topicName);
        if (topic == null) throw new IllegalArgumentException("Unknown topic: " + topicName);
        
        // Hash partition key to determine partition (ordering guarantee)
        int partition = Math.abs(partitionKey.hashCode()) % topic.partitionCount;
        topic.partitions[partition].offer(message);
        
        // Notify subscribers
        dispatchPool.submit(() -> topic.dispatch(partition));
    }
    
    void subscribe(String topicName, String groupId, MessageHandler handler) {
        Topic topic = topics.get(topicName);
        topic.addSubscriber(groupId, handler);
    }
    
    static class Topic {
        final String name;
        final int partitionCount;
        final BlockingQueue<Message>[] partitions;
        final Map<String, ConsumerGroup> groups = new ConcurrentHashMap<>();
        
        @SuppressWarnings("unchecked")
        Topic(String name, int partitions) {
            this.name = name;
            this.partitionCount = partitions;
            this.partitions = new LinkedBlockingQueue[partitions];
            for (int i = 0; i < partitions; i++) {
                this.partitions[i] = new LinkedBlockingQueue<>();
            }
        }
        
        void addSubscriber(String groupId, MessageHandler handler) {
            groups.computeIfAbsent(groupId, k -> new ConsumerGroup())
                  .addConsumer(handler);
        }
        
        void dispatch(int partition) {
            Message message = partitions[partition].poll();
            if (message == null) return;
            
            for (ConsumerGroup group : groups.values()) {
                // Each group gets the message once (load-balanced across consumers)
                MessageHandler consumer = group.getConsumerForPartition(partition);
                try {
                    consumer.handle(message);
                } catch (Exception e) {
                    // Retry logic / dead letter queue
                }
            }
        }
    }
    
    static class ConsumerGroup {
        private final List<MessageHandler> consumers = new CopyOnWriteArrayList<>();
        
        void addConsumer(MessageHandler handler) {
            consumers.add(handler);
        }
        
        MessageHandler getConsumerForPartition(int partition) {
            // Sticky assignment: same consumer always handles same partition
            // This ensures ordering within a partition for this consumer
            return consumers.get(partition % consumers.size());
        }
    }
    
    @FunctionalInterface
    interface MessageHandler {
        void handle(Message message);
    }
}
```

---

## Design Problem 6: Design a Distributed Lock Service

**Asked at:** Amazon, Google, Microsoft

```java
class DistributedLockService {
    private final ConcurrentHashMap<String, LockEntry> locks = new ConcurrentHashMap<>();
    private final ScheduledExecutorService cleaner = Executors.newScheduledThreadPool(1);
    
    DistributedLockService() {
        // Cleanup expired locks every second
        cleaner.scheduleAtFixedRate(this::cleanupExpiredLocks, 1, 1, TimeUnit.SECONDS);
    }
    
    // Acquire lock with timeout and TTL
    boolean acquire(String lockName, String ownerId, Duration ttl, Duration waitTimeout) 
            throws InterruptedException {
        long deadline = System.nanoTime() + waitTimeout.toNanos();
        
        while (System.nanoTime() < deadline) {
            LockEntry newEntry = new LockEntry(ownerId, System.currentTimeMillis() + ttl.toMillis());
            LockEntry existing = locks.putIfAbsent(lockName, newEntry);
            
            if (existing == null) {
                return true;  // Acquired!
            }
            
            // Check if existing lock expired
            if (existing.isExpired()) {
                if (locks.replace(lockName, existing, newEntry)) {
                    return true;  // Took over expired lock
                }
            }
            
            // Wait and retry
            Thread.sleep(50);
        }
        return false;  // Timeout
    }
    
    // Release lock (only owner can release)
    boolean release(String lockName, String ownerId) {
        LockEntry entry = locks.get(lockName);
        if (entry != null && entry.ownerId.equals(ownerId)) {
            return locks.remove(lockName, entry);
        }
        return false;  // Not owner or lock doesn't exist
    }
    
    // Extend lock TTL (heartbeat/renewal)
    boolean extend(String lockName, String ownerId, Duration extension) {
        LockEntry entry = locks.get(lockName);
        if (entry != null && entry.ownerId.equals(ownerId) && !entry.isExpired()) {
            LockEntry extended = new LockEntry(ownerId, 
                System.currentTimeMillis() + extension.toMillis());
            return locks.replace(lockName, entry, extended);
        }
        return false;
    }
    
    // Fencing token (monotonically increasing, prevents stale lock holders)
    private final AtomicLong fencingCounter = new AtomicLong(0);
    
    OptionalLong acquireWithFencing(String lockName, String ownerId, Duration ttl) {
        LockEntry entry = new LockEntry(ownerId, 
            System.currentTimeMillis() + ttl.toMillis(),
            fencingCounter.incrementAndGet());
        
        if (locks.putIfAbsent(lockName, entry) == null) {
            return OptionalLong.of(entry.fencingToken);
        }
        return OptionalLong.empty();
    }
    
    private void cleanupExpiredLocks() {
        locks.entrySet().removeIf(e -> e.getValue().isExpired());
    }
    
    static class LockEntry {
        final String ownerId;
        final long expiresAt;
        final long fencingToken;
        
        LockEntry(String ownerId, long expiresAt) {
            this(ownerId, expiresAt, 0);
        }
        
        LockEntry(String ownerId, long expiresAt, long fencingToken) {
            this.ownerId = ownerId;
            this.expiresAt = expiresAt;
            this.fencingToken = fencingToken;
        }
        
        boolean isExpired() {
            return System.currentTimeMillis() > expiresAt;
        }
    }
}
```

---

## Design Problem 7: Design a Metrics Collection System

**Asked at:** Datadog, New Relic, Amazon (Staff level)

```java
class MetricsCollector {
    // High-performance counter using LongAdder (avoid CAS contention)
    private final ConcurrentHashMap<String, LongAdder> counters = new ConcurrentHashMap<>();
    
    // Histogram using ConcurrentSkipListMap for percentile calculation
    private final ConcurrentHashMap<String, Histogram> histograms = new ConcurrentHashMap<>();
    
    // Gauge (current value)
    private final ConcurrentHashMap<String, AtomicLong> gauges = new ConcurrentHashMap<>();
    
    void incrementCounter(String name, Map<String, String> tags) {
        String key = buildKey(name, tags);
        counters.computeIfAbsent(key, k -> new LongAdder()).increment();
    }
    
    void recordHistogram(String name, long value, Map<String, String> tags) {
        String key = buildKey(name, tags);
        histograms.computeIfAbsent(key, k -> new Histogram()).record(value);
    }
    
    void setGauge(String name, long value, Map<String, String> tags) {
        String key = buildKey(name, tags);
        gauges.computeIfAbsent(key, k -> new AtomicLong()).set(value);
    }
    
    // Lock-free histogram using ring buffer
    static class Histogram {
        private static final int BUFFER_SIZE = 1024;  // Power of 2
        private final long[] values = new long[BUFFER_SIZE];
        private final AtomicInteger index = new AtomicInteger(0);
        
        void record(long value) {
            int i = index.getAndIncrement() & (BUFFER_SIZE - 1);  // Wrap around
            values[i] = value;
        }
        
        // Calculate percentile (approximate for recent window)
        long percentile(double p) {
            long[] sorted = Arrays.copyOf(values, BUFFER_SIZE);
            Arrays.sort(sorted);
            int idx = (int) Math.ceil(p / 100.0 * BUFFER_SIZE) - 1;
            return sorted[Math.max(0, idx)];
        }
        
        long p50() { return percentile(50); }
        long p95() { return percentile(95); }
        long p99() { return percentile(99); }
    }
    
    // Periodic flush to backend (e.g., every 10 seconds)
    @Scheduled(fixedRate = 10000)
    void flush() {
        Map<String, Long> counterSnapshot = new HashMap<>();
        counters.forEach((key, adder) -> {
            counterSnapshot.put(key, adder.sumThenReset());
        });
        
        Map<String, Map<String, Long>> histogramSnapshot = new HashMap<>();
        histograms.forEach((key, hist) -> {
            histogramSnapshot.put(key, Map.of(
                "p50", hist.p50(),
                "p95", hist.p95(),
                "p99", hist.p99()
            ));
        });
        
        // Send to metrics backend (Prometheus, Datadog, etc.)
        metricsBackend.send(counterSnapshot, histogramSnapshot, gauges);
    }
    
    private String buildKey(String name, Map<String, String> tags) {
        if (tags == null || tags.isEmpty()) return name;
        StringBuilder sb = new StringBuilder(name);
        tags.entrySet().stream().sorted(Map.Entry.comparingByKey())
            .forEach(e -> sb.append("|").append(e.getKey()).append("=").append(e.getValue()));
        return sb.toString();
    }
}
```

---

## Design Problem 8: Implement a Simple Actor System

**Asked at:** LinkedIn, Uber, financial companies

```java
// Actor Model: Each actor processes messages sequentially (no shared state!)
// Concurrency achieved by having many actors running in parallel

abstract class Actor {
    private final String id;
    private final BlockingQueue<Message> mailbox = new LinkedBlockingQueue<>();
    private final ExecutorService executor;
    private volatile boolean running = true;
    
    Actor(String id, ExecutorService executor) {
        this.id = id;
        this.executor = executor;
        // Start processing loop
        executor.submit(this::processLoop);
    }
    
    // Send message to this actor (non-blocking)
    void tell(Message message) {
        mailbox.offer(message);
    }
    
    // Processing loop: sequential message processing (no concurrency within actor!)
    private void processLoop() {
        while (running) {
            try {
                Message msg = mailbox.poll(100, TimeUnit.MILLISECONDS);
                if (msg != null) {
                    onReceive(msg);  // Handle one message at a time
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                onError(e);
            }
        }
    }
    
    // Subclass implements message handling
    protected abstract void onReceive(Message message);
    
    protected void onError(Exception e) {
        System.err.println("Actor " + id + " error: " + e.getMessage());
    }
    
    void stop() { running = false; }
}

// Example: Bank Account Actor
class AccountActor extends Actor {
    private double balance = 0;
    private final ActorSystem system;
    
    AccountActor(String id, ActorSystem system) {
        super(id, system.getExecutor());
        this.system = system;
    }
    
    @Override
    protected void onReceive(Message message) {
        switch (message) {
            case DepositMessage d -> {
                balance += d.amount();
                d.replyTo().tell(new BalanceMessage(balance));
            }
            case WithdrawMessage w -> {
                if (balance >= w.amount()) {
                    balance -= w.amount();
                    w.replyTo().tell(new SuccessMessage(balance));
                } else {
                    w.replyTo().tell(new FailureMessage("Insufficient funds"));
                }
            }
            case GetBalanceMessage g -> {
                g.replyTo().tell(new BalanceMessage(balance));
            }
            default -> System.err.println("Unknown message: " + message);
        }
    }
}

// Actor System (manages actors)
class ActorSystem {
    private final Map<String, Actor> actors = new ConcurrentHashMap<>();
    private final ExecutorService executor;
    
    ActorSystem(int threads) {
        this.executor = Executors.newFixedThreadPool(threads);
    }
    
    <T extends Actor> T createActor(String id, Function<ActorSystem, T> factory) {
        T actor = factory.apply(this);
        actors.put(id, actor);
        return actor;
    }
    
    Actor getActor(String id) {
        return actors.get(id);
    }
    
    ExecutorService getExecutor() { return executor; }
    
    void shutdown() {
        actors.values().forEach(Actor::stop);
        executor.shutdown();
    }
}
```

---

## Key Behavioral Questions for Staff Engineer

### Q248: "Tell me about a time you debugged a complex production issue"

**Framework (STAR + Technical Depth):**
```
SITUATION: "Our payment service started returning 5% errors during peak traffic"
TASK: "I needed to identify the root cause and fix it without taking the service down"
ACTION: 
1. "Checked metrics dashboard - saw HikariCP active connections at max (10/10)"
2. "Took thread dump - 8 threads blocked waiting for DB connection"
3. "The 2 active connections were running slow queries (>30s)"
4. "Traced to a new feature that did N+1 queries (100 orders × 5 items = 500 queries)"
5. "Immediate fix: Increased pool to 20, set query timeout to 5s"
6. "Root fix: Added @EntityGraph for eager loading, reduced to 1 query"
RESULT: "Error rate dropped to 0%, p99 latency reduced from 30s to 200ms"
FOLLOW-UP: "Added pool exhaustion alerts, query timeout defaults, and N+1 detection in CI"
```

### Q249: "How would you design a system to handle 1M events/second?"

**Framework:**
```
1. CLARIFY: What kind of events? Processing latency requirements? Ordering needs?
2. BACK-OF-ENVELOPE: 1M/s × 1KB = 1GB/s throughput, ~86B events/day
3. ARCHITECTURE:
   - Ingestion: Kafka (partitioned by event key, 100 partitions)
   - Processing: Flink/Kafka Streams (stateful processing)
   - Storage: Time-series DB (InfluxDB/TimescaleDB) + Object store (S3)
   - Query: Pre-aggregated materialized views
4. JAVA SPECIFICS:
   - Netty-based ingestion (non-blocking, 100K connections/instance)
   - Off-heap memory for buffers (avoid GC on hot path)
   - ZGC or no-GC (Epsilon) for latency-sensitive components
   - Batch writes to reduce I/O (buffer 1000 events, flush every 100ms)
5. FAILURE HANDLING:
   - At-least-once delivery (Kafka consumer offsets)
   - Idempotent processing (deduplication with event ID)
   - Dead letter queue for poison messages
6. SCALING:
   - Horizontal: More Kafka partitions + consumers
   - Vertical: Bigger instances for stateful operators
```

---

