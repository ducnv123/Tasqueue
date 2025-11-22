# CLAUDE.md - Tasqueue Developer Guide

This document provides a comprehensive guide for AI assistants (and developers) working with the Tasqueue codebase.

## Project Overview

**Tasqueue** is a lightweight, distributed job/worker implementation in Go that provides a simple yet powerful task queue system.

- **Language**: Go 1.21+
- **License**: BSD-2-Clause-FreeBSD
- **Module**: `github.com/kalbhor/tasqueue/v2`
- **Main Author**: Lakshay Kalbhor (@kalbhor)
- **Organization**: Zerodha

### Key Features
- Distributed job/task processing
- Support for individual jobs, groups (parallel), and chains (sequential)
- Pluggable broker and results backends (Redis, NATS JetStream, in-memory)
- Job lifecycle callbacks (processing, success, retrying, failed)
- Scheduled/delayed job execution with cron support
- Job timeout and retry mechanisms
- OpenTelemetry tracing support
- OnSuccess/OnError job chaining

## Repository Structure

```
/
├── server.go           # Main server implementation and task processing
├── jobs.go             # Job creation, enqueueing, and message handling
├── groups.go           # Group (parallel jobs) implementation
├── chains.go           # Chain (sequential jobs) implementation
├── interfaces.go       # Broker and Results interface definitions
├── go.mod              # Go module dependencies
├── README.md           # User-facing documentation
├── LICENSE             # BSD-2-Clause license
│
├── brokers/            # Broker implementations
│   ├── redis/          # Redis broker
│   ├── nats-js/        # NATS JetStream broker
│   └── in-memory/      # In-memory broker (testing)
│
├── results/            # Results store implementations
│   ├── redis/          # Redis results store
│   ├── nats-js/        # NATS JetStream results store
│   └── in-memory/      # In-memory results store (testing)
│
├── examples/           # Example applications
│   ├── redis/          # Redis-backed example
│   ├── nats-js/        # NATS-backed example
│   ├── in-memory/      # In-memory example with OpenTelemetry
│   └── tasks/          # Example task handlers
│
├── .github/
│   └── workflows/
│       └── test.yml    # CI/CD pipeline
│
└── *_test.go           # Test files alongside source
```

## Core Architecture & Concepts

### 1. Server (`server.go`)

The `Server` is the central component that:
- Holds broker and results store interfaces
- Manages task registration and queue configuration
- Coordinates job consumption and processing
- Handles job lifecycle and state transitions

**Key Types:**
```go
type Server struct {
    log       *slog.Logger
    broker    Broker
    results   Results
    cron      *cron.Cron
    traceProv *trace.TracerProvider
    tasks     map[string]Task     // Registered task handlers
    queues    map[string]uint32   // Queue -> concurrency mapping
    defaultConc int
}

type ServerOpts struct {
    Broker        Broker          // Required
    Results       Results         // Required
    Logger        slog.Handler    // Optional
    TraceProvider *trace.TracerProvider // Optional
}
```

### 2. Task

A `Task` is a pre-registered job handler with callbacks.

```go
type Task struct {
    name    string
    handler handler  // func([]byte, JobCtx) error
    opts    TaskOpts
}

type TaskOpts struct {
    Concurrency  uint32
    Queue        string
    SuccessCB    func(JobCtx)
    ProcessingCB func(JobCtx)
    RetryingCB   func(JobCtx, error)
    FailedCB     func(JobCtx, error)
}
```

**Important**: Once a queue is created with a specific concurrency, you cannot change it. Subsequent tasks using the same queue must use the same concurrency value.

### 3. Job (`jobs.go`)

A `Job` represents a unit of work:
- Contains a `[]byte` payload (handler's responsibility to decode)
- References a task by name
- Supports OnSuccess/OnError chaining
- Can be scheduled or delayed

```go
type Job struct {
    OnSuccess []*Job
    Task      string
    Payload   []byte
    OnError   []*Job
    Opts      JobOpts
}

type JobOpts struct {
    ID         string        // Optional, auto-generated if empty
    ETA        time.Time     // Execute at specific time
    Queue      string
    MaxRetries uint32
    Schedule   string        // Cron schedule
    Timeout    time.Duration
}
```

### 4. Job States

Jobs transition through these states:
- `queued` (StatusStarted) - Initial state when enqueued
- `processing` (StatusProcessing) - Worker received the job
- `retrying` (StatusRetrying) - Job failed, retrying
- `successful` (StatusDone) - Job completed successfully
- `failed` (StatusFailed) - Job failed after max retries

### 5. Interfaces (`interfaces.go`)

**Broker Interface** - Queue operations:
```go
type Broker interface {
    Enqueue(ctx, msg []byte, queue string) error
    EnqueueScheduled(ctx, msg []byte, queue string, ts time.Time) error
    Consume(ctx, work chan []byte, queue string)
    GetPending(ctx, queue string) ([]string, error)
}
```

**Results Interface** - Job metadata and results storage:
```go
type Results interface {
    Get(ctx, id string) ([]byte, error)
    Set(ctx, id string, b []byte) error
    DeleteJob(ctx, id string) error
    GetFailed(ctx) ([]string, error)
    GetSuccess(ctx) ([]string, error)
    SetFailed(ctx, id string) error
    SetSuccess(ctx, id string) error
    NilError() error  // For checking missing keys
}
```

### 6. Groups (`groups.go`)

Groups execute multiple jobs in parallel. The group is successful only if all jobs succeed.

```go
type Group struct {
    Jobs []Job
    Opts GroupOpts
}
```

### 7. Chains (`chains.go`)

Chains execute jobs sequentially, passing results between jobs via `JobCtx.Meta.PrevJobResult`.

```go
type Chain struct {
    Jobs []Job  // Executed in order
    Opts ChainOpts
}
```

## Development Workflows

### Running Tests

```bash
# Run all tests with coverage
go test -v ./... -covermode=count -coverprofile=coverage.out

# View coverage report
go tool cover -func=coverage.out

# Run tests for specific package
go test -v ./brokers/redis
```

### CI/CD

GitHub Actions workflow (`.github/workflows/test.yml`):
- Triggers on push and pull requests
- Uses Go 1.21
- Runs `go mod verify`
- Executes test suite with coverage
- Verifies README.md hasn't changed unexpectedly

### Adding a New Broker

1. Create directory: `brokers/<broker-name>/`
2. Implement the `Broker` interface
3. Handle atomicity to prevent duplicate job consumption
4. Add example in `examples/<broker-name>/`
5. Update README.md

### Adding a New Results Backend

1. Create directory: `results/<backend-name>/`
2. Implement the `Results` interface
3. Properly implement `NilError()` for key-not-found errors
4. Add example in `examples/<backend-name>/`
5. Update README.md

## Code Conventions & Patterns

### General Go Conventions

1. **Error Handling**: Always check and handle errors explicitly
2. **Context Usage**: Pass `context.Context` as first parameter
3. **Logging**: Use structured logging with `slog`
4. **Locking**: Use RWMutex appropriately (see `server.go` patterns)
5. **Serialization**: Use `msgpack` for job message encoding

### Naming Conventions

- **Exported Types**: PascalCase (Server, Job, Task)
- **Unexported Types**: camelCase (handler)
- **Interfaces**: Noun form (Broker, Results)
- **Methods**: Verb form (Enqueue, RegisterTask)
- **Constants**: StatusDone, StatusFailed, etc.

### Important Patterns

#### 1. Message Prefixing
Different entity types use prefixes for storage keys:
```go
const jobPrefix = "job:msg:"
const groupPrefix = "group:msg:"
const chainPrefix = "chain:msg:"
```

#### 2. Msgpack Serialization
All messages are serialized with msgpack:
```go
b, err := msgpack.Marshal(msg)
// ...
err = msgpack.Unmarshal(b, &msg)
```

#### 3. Context for Cancellation
Jobs can be cancelled via context:
```go
jctx, cancelFunc := context.WithCancel(ctx)
// or with timeout
jctx, cancelFunc := context.WithDeadline(ctx, deadline)
```

#### 4. OpenTelemetry Spans
When tracing is enabled, create spans for operations:
```go
var span spans.Span
if s.traceProv != nil {
    ctx, span = otel.Tracer(tracer).Start(ctx, "operation_name")
    defer span.End()
}
```

#### 5. Loop Variable Capture Fix
When capturing loop variables in goroutines:
```go
for q, conc := range queues {
    q := q  // Hack to fix loop variable capture issue
    go func() {
        s.consume(ctx, work, q)
    }()
}
```

### Concurrency Patterns

1. **Queue Processing**: Each queue has `concurrency` number of processor goroutines
2. **Work Channels**: Unbuffered channels pass jobs from consumer to processors
3. **WaitGroups**: Used in `Start()` to coordinate goroutine lifecycle
4. **RWMutex**: Protects `tasks` and `queues` maps with read/write locks

## Testing Guidelines

### Test File Organization

- Place tests in `*_test.go` files alongside source
- Use table-driven tests where appropriate
- Test both success and failure paths

### Test Utilities

Common pattern in `server_test.go`:
```go
func newServer(t *testing.T, taskName string, handler handler) *Server {
    // Create in-memory broker and results
    // Register task
    // Return configured server
}
```

### Testing Async Operations

Since jobs are processed asynchronously, tests use `time.Sleep()`:
```go
go srv.Start(ctx)
uuid, err := srv.Enqueue(ctx, job)
// Wait for processing
time.Sleep(2 * time.Second)
msg, err := srv.GetJob(ctx, uuid)
```

### Key Test Scenarios

1. **Job Enqueueing**: Verify jobs can be enqueued
2. **Status Transitions**: Check job status changes correctly
3. **Retries**: Test max retry behavior
4. **Timeouts**: Verify timeout handling
5. **Callbacks**: Test all lifecycle callbacks
6. **Results**: Verify `JobCtx.Save()` persists data
7. **Groups**: Test parallel job execution
8. **Chains**: Test sequential job execution with result passing
9. **OnError/OnSuccess**: Test conditional job enqueueing

## Common Tasks & Examples

### Creating and Registering a Task

```go
func SumProcessor(b []byte, m tasqueue.JobCtx) error {
    var payload SumPayload
    if err := json.Unmarshal(b, &payload); err != nil {
        return err
    }

    result, err := json.Marshal(SumResult{
        Result: payload.Arg1 + payload.Arg2,
    })
    if err != nil {
        return err
    }

    // Save results for later retrieval
    return m.Save(result)
}

// Register
err := srv.RegisterTask("add", SumProcessor, tasqueue.TaskOpts{
    Queue: "math_operations",
    Concurrency: 5,
    SuccessCB: func(jc JobCtx) {
        log.Println("Job succeeded:", jc.Meta.ID)
    },
})
```

### Creating and Enqueueing Jobs

```go
payload, _ := json.Marshal(SumPayload{Arg1: 5, Arg2: 3})
job, err := tasqueue.NewJob("add", payload, tasqueue.JobOpts{
    MaxRetries: 3,
    Timeout: 30 * time.Second,
})

jobID, err := srv.Enqueue(ctx, job)
```

### Creating a Chain

```go
var jobs []tasqueue.Job
for i := 0; i < 3; i++ {
    payload, _ := json.Marshal(Data{Value: i})
    job, _ := tasqueue.NewJob("process", payload, tasqueue.JobOpts{})
    jobs = append(jobs, job)
}

chain, err := tasqueue.NewChain(jobs, tasqueue.ChainOpts{})
chainID, err := srv.EnqueueChain(ctx, chain)
```

### Accessing Previous Job Results in a Chain

```go
func ChainedHandler(b []byte, jc tasqueue.JobCtx) error {
    // Access previous job's saved results
    if jc.Meta.PrevJobResult != nil {
        var prevResult PreviousResult
        json.Unmarshal(jc.Meta.PrevJobResult, &prevResult)
        // Use prevResult...
    }
    // Process current job...
}
```

### Using OnError Handlers

```go
mainJob, _ := tasqueue.NewJob("risky_task", payload, tasqueue.JobOpts{
    MaxRetries: 2,
})

cleanupJob, _ := tasqueue.NewJob("cleanup", nil, tasqueue.JobOpts{})
mainJob.OnError = append(mainJob.OnError, &cleanupJob)

srv.Enqueue(ctx, mainJob)
// If risky_task fails after retries, cleanup will be enqueued
```

## Key Files Reference

### Core Files
- `server.go:66-96` - `RegisterTask()` validates queue concurrency
- `server.go:210-242` - `Start()` spawns consumer and processor goroutines
- `server.go:300-414` - `execJob()` handles full job lifecycle
- `jobs.go:120-186` - `Enqueue()` and `enqueueWithMeta()` handle job enqueueing
- `jobs.go:64-76` - `DefaultMeta()` generates job metadata

### State Management
- `server.go:467-563` - Status transition methods (statusStarted, statusProcessing, etc.)
- `server.go:416-442` - `retryJob()` implements retry logic

### Serialization
- `jobs.go:232-250` - `setJobMessage()` stores job state
- `groups.go:141-147` - `setGroupMessage()` stores group state
- `chains.go:137-143` - `setChainMessage()` stores chain state

### Interfaces
- `interfaces.go:8-19` - Results interface
- `interfaces.go:21-34` - Broker interface

## Important Considerations

### Thread Safety
- Server uses `sync.RWMutex` to protect shared maps
- Always acquire locks when accessing `tasks` or `queues` maps
- Pattern: RLock for reads, Lock for writes

### Queue Concurrency Immutability
Once a queue is created with a concurrency value, it cannot be changed. This is enforced in `RegisterTask()`:
```go
// server.go:87-95
if opts.Concurrency == conc {
    s.registerHandler(name, Task{...})
    return nil
}
return fmt.Errorf("queue is already defined with %d concurrency", conc)
```

### Job Handler Responsibilities
- Handlers must decode the `[]byte` payload themselves
- Return `error` to trigger retries
- Use `JobCtx.Save([]byte)` to persist results
- Access job metadata via `JobCtx.Meta`

### Error Handling in Chains
If a job in a chain fails after max retries:
- Chain status becomes `StatusFailed`
- Subsequent jobs in the chain are NOT enqueued
- `OnError` jobs (if configured) are enqueued

### Scheduled Jobs
Jobs with a `Schedule` cron expression automatically create a new job via `OnSuccess` to maintain the schedule:
```go
// jobs.go:136-160
if t.Opts.Schedule != "" {
    sch, err := cron.ParseStandard(t.Opts.Schedule)
    // Creates next job with OnSuccess
    t.OnSuccess = append(t.OnSuccess, &j)
    j.Opts.ETA = sch.Next(t.Opts.ETA)
}
```

## Contributing Guidelines

When making changes:
1. **Run tests** before committing
2. **Update README.md** if changing public API
3. **Add tests** for new features
4. **Follow existing patterns** in the codebase
5. **Use structured logging** instead of `fmt.Println`
6. **Add OpenTelemetry spans** for new operations if tracing is important
7. **Handle errors explicitly** - no silent failures
8. **Document complex logic** with comments

## Common Pitfalls to Avoid

1. **Don't modify queue concurrency** after creation
2. **Don't skip error handling** in handlers - return errors to trigger retries
3. **Don't block indefinitely** in handlers - respect job timeouts
4. **Don't assume job order** - even in chains, timing can vary
5. **Don't forget to call `Save()`** if you want to persist job results
6. **Don't use unbuffered operations** in handlers without timeout protection
7. **Don't access server internals** directly - use provided methods

## Additional Resources

- **Examples**: See `examples/` directory for complete working examples
- **Task Handlers**: See `examples/tasks/tasks.go` for handler patterns
- **Tests**: See `*_test.go` files for usage examples
- **README.md**: User-facing documentation
- **Go Report Card**: https://goreportcard.com/report/github.com/kalbhor/tasqueue/v2

---

*This document was generated for AI assistants to better understand and work with the Tasqueue codebase.*
